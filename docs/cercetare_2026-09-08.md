# Technical brief: Shopify -> GitHub Pages -> Favi product feed (verified research, 2026-09-08)

## 1. Shopify custom app click path (current, non-Plus merchant)

Context: since 2026-01-01 new custom apps cannot be created in the Shopify admin; they are built in the Dev Dashboard and installed on the store. No permanent "Admin API access token" is shown anywhere for new apps; you exchange Client ID + Client secret for a 24-hour token. Legacy admin-created apps (pre-2026) keep working.

1. Sign in to the Shopify admin (https://admin.shopify.com/store/<store-handle>) as the store owner. [DISAGREEMENT - staff access: the custom-apps help page says staff need the store-level "App development" > "Develop" permission; the Dev Dashboard user-permissions docs and "Roles managed by Shopify" say staff need the organization-level "App developer" role (Plus: custom role with "Build and manage apps"). Store-level permissions are documented for the legacy admin flow only. Collaborator accounts cannot use a client's Dev Dashboard; a partner must build the app in their own organization and hand over a Custom distribution install link.]
2. Left sidebar (bottom-left): click "Settings", then click "Apps" (https://admin.shopify.com/settings/apps). [DISAGREEMENT - one verifier cites the path as "Settings > Apps and sales channels > Develop apps"; the current help-center page uses "Apps". Look for either label.]
3. Click "Develop apps".
4. Click "Build apps in Dev Dashboard" -> opens https://dev.shopify.com/dashboard/ (can also be opened directly). There is no "Allow custom app development" confirmation step in the current flow (it existed only for legacy apps).
5. In the Dev Dashboard, with "Apps" selected in the left panel, click "Create app" (top right).
6. Select "Start from Dev Dashboard" (not the Shopify CLI option).
7. Enter an app name (e.g. "Favi feed reader"), click "Create".
8. Open the "Versions" tab: (a) App URL: keep default https://shopify.dev/apps/default-app-home; (b) "Webhooks API version": pick the newest; (c) "Access" section: enter only `read_products` (write scopes include read; exact widget - free text vs picker - unverified); (d) click "Release" (if a version-details form appears, optionally fill it, click "Release" again).
9. Left panel "Home" -> scroll to "Installs" -> click "Install app".
10. If the organization has several stores, select the store (same organization only), click "Install". This grants `read_products`.
11. Left panel "Settings" -> "Credentials" -> copy "Client ID" and "Client secret". No Admin API access token is displayed.
12. Get a token programmatically (client credentials grant):
    `POST https://<store-handle>.myshopify.com/admin/oauth/access_token`
    `Content-Type: application/x-www-form-urlencoded`
    body: `grant_type=client_credentials&client_id=<Client ID>&client_secret=<Client secret>`
    Response: `{"access_token":"...","scope":"read_products","expires_in":86399}` (24 h, no refresh token - just request a new one). Do not hard-code a token prefix check (docs conflict: bare hex example vs "shpat_").
13. Rotate secret: Dev Dashboard > "Apps" > app > "Settings" > "Credentials" > "Rotate" > "Generate new secret"; old secret stays active until revoked (revoking kills tokens issued with it).
14. Change scopes later: release a new version ("Versions" > edit > "Release"); the merchant must approve the new scopes on the store.
15. Uninstall: admin "Settings" > "Apps" > "..." next to the app > "Uninstall" > "Uninstall". Delete: "Settings" > "Apps" > "Develop apps" > "Build apps in Dev Dashboard" > app > "Settings" > "Delete app" > confirm (irreversible).
16. Store handle: admin "Settings" > "Domains" shows `<handle>.myshopify.com`; also visible in the admin URL. API base = `https://<handle>.myshopify.com`. Handle can be changed once - stable but not immutable.

Legacy path (apps created before 2026-01-01 only): "Settings" > "Apps" > "Legacy custom apps" section > app > "API credentials" tab. The `shpat_` token was shown once ("Reveal token once" label not re-confirmed for 2026). New token = uninstall + reinstall from admin. Never delete a legacy app (cannot be recreated).

## 2. Shopify GraphQL Admin API

- Latest stable: **2026-07** (accessible until 2027-07-16 15:00 UTC). 2026-10 is the release candidate (callable since 2026-07-01, `supported=false`, not for production). Currently accessible stable versions: 2025-10 (closes 2026-10-16), 2026-01, 2026-04, 2026-07. Requests to an expired version "fall forward" to the oldest accessible stable version; verify via the `X-Shopify-API-Version` response header.
- Endpoint: `POST https://{shop}.myshopify.com/admin/api/2026-07/graphql.json`, headers `Content-Type: application/json` and `X-Shopify-Access-Token: {token}`, body `{"query": "...", "variables": {...}}`.
- Deprecated - do NOT use: `Product.images`, `Product.featuredImage` (use `media` / `featuredMedia`), `ProductVariant.image`, `Image.src`/`originalSrc`/`transformedSrc`; `ProductVariant.weight`/`weightUnit` no longer exist (removed after 2024-04 deprecation).

Ready-to-use query (all fields verified non-deprecated in 2026-07; `pageInfo{hasNextPage endCursor}` and `selectedOptions{name value}` sub-selections are standard connection/object shapes not separately re-verified in this research):

```graphql
query ProductsByTag($cursor: String) {
  products(first: 250, after: $cursor, query: "tag:OCEANFAVI") {
    pageInfo { hasNextPage endCursor }
    nodes {
      legacyResourceId
      handle
      title
      descriptionHtml
      vendor
      productType
      tags
      status
      onlineStoreUrl
      totalInventory
      media(first: 21, sortKey: POSITION) {
        nodes {
          ... on MediaImage {
            image { url width height }
          }
        }
      }
      variants(first: 250) {
        nodes {
          legacyResourceId
          title
          displayName
          sku
          barcode
          price
          compareAtPrice
          position
          inventoryQuantity
          selectedOptions { name value }
          inventoryItem {
            measurement { weight { value unit } }
          }
        }
      }
    }
  }
}
```

Notes:
- `media` sorted by POSITION by default (enum has only ID and POSITION); `first: 21` = 1 IMGURL + up to 20 IMGURL_ALTERNATIVE (Favi cap). `MediaImage.image` is null until media status is READY - skip nulls. `Image.width/height` are null for images not hosted by Shopify.
- Weight chain: `inventoryItem` (non-null) -> `measurement` (non-null) -> `weight` (nullable) -> `{ value: Float!, unit: GRAMS|KILOGRAMS|OUNCES|POUNDS }`. Only `weight` needs a null guard.
- `onlineStoreUrl` is null for password-protected stores, non-ACTIVE products and unpublished products (confirmed); fall back to building the URL from `handle` if needed.
- Tag matching: case-sensitivity of `tag:` is undocumented; after fetching, keep only products where `"OCEANFAVI"` is exactly in `tags`.
- Pagination: cursor-based (`after: endCursor` until `hasNextPage` is false); max 250 per page. A 25,000-object pagination cap is documented in general; for catalogs above that use `bulkOperationRunQuery` (no max-cost/rate limits).
- Throttling: calculated query cost, leaky bucket. Standard plan restores 100 points/second; bucket size is not stated numerically - read `extensions.cost.throttleStatus.{maximumAvailable,currentlyAvailable,restoreRate}` from each response instead of hard-coding. A throttled call returns HTTP 200 with `errors[i].extensions.code == "THROTTLED"` (defensively also match `message == "Throttled"`); sleep `max(0, (requestedQueryCost - currentlyAvailable) / restoreRate)` seconds and retry. If you get `MAX_COST_EXCEEDED`, reduce `first` values.

## 3. GitHub click paths, action versions, workflow skeleton

A. Create public repo: "+" icon (upper-right) > "New repository" > "Owner" dropdown > "Repository name" (e.g. feed-favi) > optional "Description" > visibility: Public [DISAGREEMENT: the redesigned form (GA 2025-08-26) uses a "Choose visibility" dropdown and an "Add README" toggle; the legacy tutorial says "Public/Private" radio and "Add a README file" checkbox] > enable README > "Create repository".

B. Secrets: repo > "Settings" (or "..." > "Settings") > sidebar "Security" section > "Secrets and variables" > "Actions" > "Secrets" tab (default tab not verified) > "New repository secret" > "Name" / "Secret" > "Add secret". Repeat per secret. (Docs example name: SHOPIFY_TOKEN; with the Dev Dashboard flow you would instead store the Client ID and Client secret and mint the 24 h token inside the workflow - derived from section 1, not a documented recipe.)

C. Pages: repo > "Settings" > sidebar > "Pages" [DISAGREEMENT on the section heading: "Code, planning, and automation" (docs changed 2026-08-24) vs "Code and automation" (other current docs, April-2026 tutorial, GHES) - just locate "Pages"] > "Build and deployment" > "Source" > select "GitHub Actions". Skip suggested templates. No branch/folder dropdown, no Save button; applies immediately. Branch is chosen by the workflow trigger (optionally restricted via a deployment-branch rule on the `github-pages` environment under Settings > Environments).

D. Workflow file: "Add file" > "Create new file" > `.github/workflows/feed.yml` > "Commit changes..." > "Commit changes" directly to the default branch (schedule only fires from the default branch).

E. Run/verify: "Actions" tab > workflow > "Run workflow" > "Run workflow". Run Summary shows `$GITHUB_STEP_SUMMARY` output; deploy job shows the github-pages environment URL. Settings > Pages shows "Your site is live at https://<owner>.github.io/<repo>/" with "Visit site". Feed URL: `https://<owner>.github.io/<repo>/oceanfavi.xml` (root of uploaded directory). Publishing can take up to 10 minutes; edge CDN observed with `Cache-Control: max-age=600` plus a proxy cache layer, so assume at least ~10 minutes (possibly longer) of staleness; verify freshness via cache-busting query string or Last-Modified/ETag.

Action versions (latest as of 2026-09-08 - pin exact versions):
- `actions/checkout@v7.0.1` (2026-07-20). Pin v7.0.1, not v7.0.0 (false-positive block fixed). The fork-PR guard affects only pull_request_target / workflow_run-from-PR events, not schedule/push/workflow_dispatch; note it was backported to floating tags v6.1.0/v5.1.0/v4.4.0/v3.7.0/v2.8.0. Requires node24 runner (>= v2.327.1, since v5).
- `actions/setup-python@v7.0.0` (2026-07-20; ESM, `pip-install` input removed).
- `actions/configure-pages@v6.0.0`, `actions/upload-pages-artifact@v5.0.0`, `actions/deploy-pages@v5.0.1` (Node 24; upload-artifact v7 underneath). Open: no doc confirms a required pairing of upload-pages-artifact v5 with deploy-pages v5; GitHub's own docs example still shows checkout@v6 / configure-pages@v5 / upload-pages-artifact@v4 / deploy-pages@v4 and the starter shows checkout@v4 / configure-pages@v5 / upload-pages-artifact@v3 / deploy-pages@v5.

Minimal skeleton (modelled on the GitHub Pages starter):

```yaml
name: Build Favi feed
on:
  schedule:
    - cron: "0 */2 * * *"
  workflow_dispatch:
  push:
    branches: [main]
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: "pages"
  cancel-in-progress: false
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7.0.1
      - uses: actions/setup-python@v7.0.0
        with:
          python-version: "3.x"
      - name: Build feed XML into ./public
        env:
          SHOPIFY_CLIENT_ID: ${{ secrets.SHOPIFY_CLIENT_ID }}
          SHOPIFY_CLIENT_SECRET: ${{ secrets.SHOPIFY_CLIENT_SECRET }}
        run: python build_feed.py   # writes public/oceanfavi.xml
      - uses: actions/configure-pages@v6.0.0
      - uses: actions/upload-pages-artifact@v5.0.0
        with:
          path: public
          # retention-days: 1 (default); raise for debugging
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v5.0.1
```

## 4. Favi feed spec essentials

- Docs: help.favionline.com (RO/EN). Format: Heureka XML, `<?xml version="1.0" encoding="utf-8"?>`, root `<SHOP>`, one `<SHOPITEM>` per variant.
- REQUIRED (exactly 8): `ITEM_ID`, `PRODUCTNAME`, `DESCRIPTION`, `CATEGORYTEXT`, `PRICE_VAT`, `URL`, `IMGURL`, `DELIVERY_DATE`.
- RECOMMENDED: `ITEMGROUP_ID`, `IMGURL_ALTERNATIVE` (max 20), `PARAM{PARAM_NAME,VAL}`, `DELIVERY{DELIVERY_ID,DELIVERY_PRICE,DELIVERY_PRICE_COD}`, `EAN`, `MANUFACTURER`.
- NOT documented by Favi: `VAT`, `HEUREKA_CPC`, `PRODUCTNO`, `PRODUCT` (PRODUCT appears in Favi's example PDF as a duplicate of PRODUCTNAME). Safest: omit them.
- `ITEM_ID`: unique, never changes for the life of the cooperation; digits, ASCII letters, dashes, underscores only; duplicates are an error. `ITEMGROUP_ID`: shared by variants of one product, each with its own ITEM_ID.
- `PRODUCTNAME`: descriptive; must not contain shop name, URL, stock status, discounts, promotions or free-shipping text.
- `CATEGORYTEXT`: exactly one, full path recommended (e.g. "Bedrooms > Beds > Single"); generic categories (sales, promotions, room names) or wrong-language categories are rejected and the product is not loaded; changing categories removes products until re-approved.
- `URL`: unique per SHOPITEM (identical URLs merge products), valid, no spaces/diacritics, special characters entity-encoded; landing page must show price, specific product information and a buy/order button. HTTPS is required for product-page and image links per the "basic information" page (and the shop must be HTTPS), though the element page states HTTPS only for `IMGURL`.
- `IMGURL` / `IMGURL_ALTERNATIVE`: HTTPS, no spaces/diacritics; plain URLs (angle brackets in the PDF are artifacts).
- `DELIVERY_DATE`: 0, 1, 2 or 3 = in stock; other bands (4-14, 15-30, 31+) extracted from a table - eyeball the EN page before relying on the wording.
- `PRICE_VAT`: plain decimal, VAT included; currency not stated anywhere - assume RON for favi.ro and confirm with the account manager.
- Heureka-format ceilings (format guidance, not Favi rules): 500,000 items, PRODUCTNAME 200 chars, ITEM_ID 36 chars, URL 300 chars. Favi states no DESCRIPTION/file-size/item-count limits.
- Dashboard: Favi partner admin > "Settings" ("Setări") > "XML Feed" tab (next to "Billing information") shows the registered feed URL and freshness. To change the URL: regenerate with the SAME ITEM_IDs and send the new URL to your Favi account manager. Default fetch: 3x/day (ask the account manager for more); a 2-hour regeneration is more than sufficient. Serve plain cacheable XML over HTTPS without bot/IP blocking (403 = "feed blocked"). Min CPCs: Partner Dashboard > Cost Per Click > Category Bids.

## 5. Refuted claims (corrected) and open questions

Refuted/corrected:
1. "Legacy flow was Settings > Apps and sales channels > Develop apps > Allow custom app development" -> Path varied: early 2021 to ~mid-2022 it was Apps > Develop apps (store owner only); Jul 2022 to Nov 2025 it was Settings > Apps and sales channels > Develop apps > "Allow custom app development" (twice; owner or staff with "Enable app development"). Not available since 2026-01-01.
2. "Staff need the store-level 'App development > Develop' permission for the Dev Dashboard" -> Docs inconsistent; the documented Dev Dashboard path is the organization-level "App developer" role (Plus: custom role with "Build and manage apps"). Collaborators cannot access a client's Dev Dashboard; partners use a Custom distribution install link from their own org.
3. "'App development' group lets staff create custom apps" -> The three sub-permissions still exist but now only govern viewing/updating/enabling legacy admin apps; shopify.dev labels the permission "Develop apps".
4. "Custom apps are created and managed in the Dev Dashboard" -> True only for NEW apps; legacy pre-2026 apps are managed in the admin. One verifier records the entry path as Settings > "Apps and sales channels" (label disagreement with "Apps").
5. "read_products grants Product, ProductVariant, Collection, ResourceFeedback, SellingPlan" -> SellingPlan queries additionally require read_purchase_options or read_own_subscription_contracts; ResourceFeedback pages require read_resource_feedbacks. For a feed reading Product/Variant/Collection, read_products alone is sufficient.
6. "Accessible versions are 2025-10, 2026-01, 2026-04, 2026-07; 2026-10 not available until Oct 1" -> Correct for STABLE versions, but the 2026-10 release candidate has been callable since 2026-07-01 (supported=false) and `unstable` is always callable. 2025-07 requests fall forward to 2025-10 (visible in X-Shopify-API-Version). 2025-10 closes 2026-10-16.
7. "InventoryItem.measurement is nullable" -> It is non-null (`InventoryItemMeasurement!`); only `measurement.weight` is nullable.
8. "New-repo form: Public/Private choice and 'Add a README file'" -> Redesigned form: "Owner" dropdown, "Repository name", "Description", "Choose visibility" dropdown (Public/Private; Internal on GHEC orgs), "Add README" toggle, optional .gitignore/license, optional Copilot "Prompt" field, "Create repository".
9. "Pages is under the 'Code, planning, and automation' sidebar section" -> Section label disputed ("Code and automation" in several current docs); locate "Pages" regardless. Rest of the path confirmed.
10. "CDN max-age=600 means at most ~10 minutes staleness" -> Empirical only; a second proxy-cache layer served objects past their Expires; assume at least ~10 minutes, possibly longer; check freshness explicitly.
11. "checkout v7.0.0's breaking change is v7-only" -> The guard was backported as [BREAKING] to v6.1.0, v5.1.0, v4.4.0, v3.7.0, v2.8.0 (floating majors inherit it); v7.0.0 over-blocked, v7.0.1 fixes it; no new runner minimum in v7.
12. "Product without a category is not loaded because category is the primary classification input" -> Products with missing OR unusable categories are not loaded (visible under product data quality in the shop overview); Favi's own FAQ says the product name is the primary placement input, category secondary.
13. "URL must be HTTPS; landing page must show specs" -> The element page states HTTPS for IMGURL, not URL; HTTPS for product-page and image links is stated on the "basic information" page (shop must be HTTPS). Landing page must show "specific information", not "specs"; Heureka adds a 300-char URL cap.

Open questions:
- Token prefix for client-credentials tokens (bare hex vs shpat_); do not check prefix.
- Exact widget for the "Access" scopes field in the Dev Dashboard version editor.
- Whether "Enable development" staff permission still gates anything for staff (not owners) in 2026.
- Whether the Dev Dashboard "Install app" picker lists a regular merchant's live store by default (not tested live).
- Exact 2026 label for the legacy "Reveal token once" button; legacy step labels beyond the four "Allow custom app development" steps are from search snippets.
- How to change scopes on a legacy admin-created app (not documented on the page fetched).
- Standard-plan bucket size (docs give 100 points/second only; JSON example shows 1000/50 and looks illustrative) - read throttleStatus at runtime.
- No verbatim THROTTLED response example found; handling rule derived from the error-code table.
- Versioning table lists 2026-10 and 2027-01 as "Stable" with future dates while the reference selector says 2026-10 is the RC - verify via response header.
- The Product.images deprecation changelog could not be fetched (404); reasons taken from the 2026-07 reference page data.
- Case-sensitivity of `tag:` search; 25,000-object pagination cap for `products(first:250)` untested; `onlineStoreUrl` null when app lacks Online Store channel access unconfirmed.
- Action version pairing (upload-pages-artifact v5 with deploy-pages v5) not documented; parts of release pages failed to load.
- GitHub Pages acceptable-use: Pages prohibits e-commerce/commercial-transaction hosting; a price-comparison feed is not a storefront but is commercial - decide whether Pages is acceptable or use another host (prohibition sentence paraphrased, not verbatim).
- CDN TTL is undocumented; "Secrets" tab default not verified; artifact retention defaults to 1 day.
- Heureka.cz official spec unreachable (TLS error); Heureka facts taken from the SK mirror (SK-specific values).
- Favi currency for PRICE_VAT unconfirmed (favi.ro returned 403); assume RON incl. VAT.
- Whether Favi ignores or validates VAT/HEUREKA_CPC/PRODUCTNO if present.
- Exact Favi reload times; whether Favi honors Last-Modified/gzip.
- Accepted DELIVERY_ID carrier codes for Romania (examples: PPL, GLS) - ask Favi, or use a generic carrier with DELIVERY_PRICE 0 for free shipping.
- DELIVERY_DATE band labels (4-14, 15-30, 31+) need visual confirmation on the EN page.
- Low-confidence third-party notes: Favi pulls on its own schedule from a permanent URL; regenerating every 2-4 h (or at least daily) is sufficient; listing/delisting after a feed change can take about half a day or more.