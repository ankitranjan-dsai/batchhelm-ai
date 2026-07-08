# Website Analysis Report: http://47.84.199.208/

**Site:** BatchHelm AI - Product Recall Command Center  
**Type:** React SPA (Single Page Application)  
**Server:** nginx/1.27.5  
**Date Analyzed:** July 8, 2026  

---

## 1. Critical Security Issues (Fix Immediately)

### 1.1 No HTTPS / Unencrypted Connection
- The site is served **exclusively over HTTP**. HTTPS connection attempts time out.
- **Risk:** All data (including potential sensitive recall information, staff names, inventory data) is transmitted in plaintext. Vulnerable to MITM attacks, credential sniffing, and session hijacking.
- **Fix:** Obtain and configure an SSL/TLS certificate (Let's Encrypt is free). Redirect all HTTP traffic to HTTPS. Enable HSTS (`Strict-Transport-Security` header).

### 1.2 Zero Authentication on API Endpoints
- **Every tested API endpoint is completely open** — no API keys, no session cookies, no JWT tokens required.
- Accessible endpoints include:
  - `GET /api/inspections/demo` — Full inspection results
  - `GET /api/evidence/demo-packet` — Complete evidence packet
  - `GET /api/evidence/demo-review` — Review decisions and checklist
  - `GET /api/qwen/status` — AI provider configuration
  - `GET /api/qwen/proof` — Verification proof data
  - `POST /api/evidence/demo-review/decision` — Can modify review decisions
  - `POST /api/intakes` — Can submit recall intakes
  - `POST /api/inspections/shelf-photo` — Can upload shelf photos
- **Risk:** Anyone on the internet can read all recall data, modify evidence review decisions, submit fake intakes, and upload files.
- **Fix:** Implement authentication (OAuth2/JWT/session-based) and authorization on ALL API routes. Use middleware to enforce it globally.

### 1.3 AI Provider Configuration Exposed
- Endpoint `/api/qwen/status` reveals:
  - Base URL: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
  - Text model: `qwen3.7-plus`
  - Vision model: `qwen3-vl-plus`
  - Mode: `live`
- Endpoint `/api/qwen/proof` reveals SHA256 verification hashes and provider request IDs.
- **Risk:** Attackers can profile your AI infrastructure, potentially exploit provider-specific vulnerabilities, or abuse your AI quota.
- **Fix:** Remove or protect internal provider configuration endpoints. Move AI keys/secrets to backend environment variables only.

### 1.4 Internal File Paths Disclosed in API Responses
- The `/api/inspections/demo` response includes:
  ```json
  "path": "sample-data/store-b-cooler-spinach.png"
  ```
- **Risk:** File path disclosure aids attackers in mapping your server filesystem and finding other accessible files or directories.
- **Fix:** Never return internal file system paths in API responses. Use opaque IDs or signed URLs instead.

### 1.5 Missing Critical Security Headers
- **No `Content-Security-Policy` (CSP)** — The app is vulnerable to XSS attacks.
- **No `X-Frame-Options` or `frame-ancestors`** — The site can be embedded in malicious iframes (clickjacking risk).
- **No `X-Content-Type-Options: nosniff`** — Browsers may MIME-sniff responses, leading to XSS.
- **No `Referrer-Policy`** — Sensitive URL data may leak to third parties.
- **No `Permissions-Policy`** — Unrestricted access to browser features (camera, geolocation, etc.).
- **Fix:** Add all of the above headers via nginx configuration or application middleware.

### 1.6 `innerHTML` Usage in JavaScript Bundle
- Found `innerHTML` usage in the compiled JavaScript bundle.
- **Risk:** Potential XSS vulnerabilities if user input is ever injected into these `innerHTML` calls without proper sanitization.
- **Fix:** Replace `innerHTML` with `textContent` or use React's built-in JSX escaping. If HTML insertion is required, use DOMPurify.

---

## 2. Privacy & Data Exposure

### 2.1 Demo Data is Fully Public
- The entire recall dataset is accessible without authentication, including:
  - **Staff names:** J. Martinez, APA. Patel, TNT. Nguyen, SJS. Johnson
  - **Store locations:** Store A, Store B, Back Room 1, Cooler A, etc.
  - **Inventory data:** SKU codes (SPN10Z), lot numbers (L2418-L2422), UPCs (008500001010), quarantine counts
  - **Task assignments and due dates**
  - **Evidence notes and confidence scores**
- **Risk:** Even if this is "demo" data, exposing it without auth suggests the same pattern may apply to production data. Also leaks business operations and supplier relationships.
- **Fix:** Gate all data behind authentication. Even demo instances should require at least a demo login.

---

## 3. Performance Issues

### 3.1 No HTTP/2 or HTTP/3 Support
- Server responds with HTTP/1.1 only.
- **Impact:** Slower page loads due to head-of-line blocking and inability to multiplex requests efficiently.
- **Fix:** Enable HTTP/2 in nginx. Consider HTTP/3 for modern browsers.

### 3.2 No Compression on Static Assets
- JS bundle (227 KB) and CSS (46 KB) are served without `Content-Encoding: gzip` or `br`.
- **Impact:** Unnecessary bandwidth usage and slower load times, especially on mobile.
- **Fix:** Enable `gzip` and `brotli` compression in nginx for JS, CSS, HTML, and JSON responses.

### 3.3 Missing Cache-Control Headers
- Static assets (JS, CSS) lack `Cache-Control` headers.
- Only `ETag` and `Last-Modified` are present.
- **Impact:** Browsers cannot efficiently cache assets. Every page load may revalidate all assets.
- **Fix:** Add aggressive cache headers for hashed assets: `Cache-Control: public, max-age=31536000, immutable`.

### 3.4 No Resource Hints
- The HTML `<head>` lacks:
  - `<link rel="preconnect">` for API origins
  - `<link rel="preload">` for critical CSS/JS/fonts
  - `<link rel="dns-prefetch">`
- **Impact:** Slower initial render and time-to-interactive.
- **Fix:** Add resource hints for the API domain and critical assets.

### 3.5 Large Monolithic JS Bundle
- Single JS bundle of ~227 KB (uncompressed).
- **Impact:** Longer parse and execution time. No code-splitting evident.
- **Fix:** Implement route-based code splitting and lazy loading with React.lazy() and Suspense.

---

## 4. SEO & Web Standards

### 4.1 Minimal Meta Tags
- Only `charset`, `viewport`, and basic `description` are present.
- **Missing:**
  - Open Graph tags (`og:title`, `og:description`, `og:image`, `og:url`)
  - Twitter Card tags
  - Canonical URL
  - Author / publisher tags
  - Theme color for mobile browsers
- **Impact:** Poor social sharing previews and SEO discoverability.
- **Fix:** Add comprehensive meta tags for better sharing and search indexing.

### 4.2 No robots.txt
- `http://47.84.199.208/robots.txt` returns the SPA HTML fallback.
- **Impact:** Search engines may index unintended pages or waste crawl budget.
- **Fix:** Add a `robots.txt` file. Block `/api/` paths from indexing.

### 4.3 No sitemap.xml
- No XML sitemap found.
- **Impact:** Reduced discoverability by search engines.
- **Fix:** Generate and serve a `sitemap.xml` for public-facing pages.

### 4.4 Missing Favicon
- No `<link rel="icon">` tag in HTML.
- **Impact:** Default browser icon shown in tabs. Looks unprofessional.
- **Fix:** Add favicon and touch icons for various devices.

### 4.5 SPA Fallback Serving Wrong Content-Type
- Nginx serves the `index.html` fallback with `Content-Type: text/html` for ALL unknown routes (e.g., `.js.map`, `.png` in `sample-data/`).
- **Impact:** Confusing for browsers and tools expecting proper content types. Can cause caching issues.
- **Fix:** Configure nginx to serve known static file types correctly and only fallback to `index.html` for SPA route paths.

---

## 5. Accessibility (a11y) Issues

### 5.1 SPA Skeleton HTML
- Raw HTML is just `<div id="root"></div>`. All content is client-side rendered.
- **Risk:** Screen readers and search engines may see an empty page initially. Users with JS disabled see nothing.
- **Fix:** Implement server-side rendering (SSR) or static site generation (SSG) for critical content. Add a `<noscript>` message.

### 5.2 Missing Skip Navigation Link
- No skip-to-content link for keyboard users.
- **Fix:** Add a visually hidden "Skip to main content" link as the first focusable element.

### 5.3 Table Accessibility
- The page contains data tables (inventory, tasks).
- Without proper markup (`<th scope="col">`, captions, aria-labels), screen reader users may struggle to understand table relationships.
- **Fix:** Ensure all tables have proper semantic markup and ARIA attributes where needed.

---

## 6. UX / UI Issues

### 6.1 "Wave" Section Shows Zero Events
- The UI shows "Wave 1" through "Wave 6" with "0" under "Execution events" and "Waiting for the first agent event."
- **Issue:** This suggests a broken or incomplete data pipeline. The section is visible but empty, which is confusing.
- **Fix:** Either hide empty sections, show a helpful empty state ("No execution events yet"), or fix the data connection.

### 6.2 "Recall Intake Agent" Shows "Pending"
- Status shows "Pending" with "Waiting for this execution stage."
- **Issue:** Unclear if this is a loading state, a user action requirement, or a system error.
- **Fix:** Use clearer status indicators (spinners for loading, clear CTAs for user action, error messages for failures).

### 6.3 Hardcoded Demo Data
- All API endpoints include `/demo/` or `/demo-` prefixes.
- **Issue:** Suggests the entire application is running in demo mode on a public server. This is risky if production data ever gets mixed in.
- **Fix:** Separate demo and production deployments. Use environment-specific configurations.

### 6.4 Upload Area Shows "Loading review controls"
- The upload section shows a persistent loading state.
- **Fix:** Add timeout handling and error states for loading indicators.

---

## 7. Backend / API Architecture Issues

### 7.1 No Rate Limiting Apparent
- No `X-RateLimit-*` headers observed.
- Multiple rapid requests were not throttled.
- **Risk:** Vulnerable to brute force, scraping, and DoS attacks.
- **Fix:** Implement rate limiting on all API endpoints (e.g., using nginx limit_req or application-level middleware).

### 7.2 CORS Configuration Concerns
- `access-control-allow-credentials: true` is set on API responses without a visible restrictive `access-control-allow-origin`.
- **Risk:** If combined with origin reflection, this would allow any website to make authenticated cross-origin requests.
- **Fix:** Explicitly define allowed origins. Never use `*` with credentials. Remove `allow-credentials` if not needed.

### 7.3 Missing Request Validation Details
- The `POST /api/intakes` endpoint returns validation errors (good), but the error format exposes internal field names (`request_id`, `notice`, `inventory`).
- **Fix:** While validation is good, ensure error messages don't leak internal schema details that could aid attackers.

### 7.4 No API Versioning
- API paths use `/api/` directly without versioning (`/api/v1/`, `/api/v2/`).
- **Risk:** Breaking changes will be difficult to roll out.
- **Fix:** Add version prefixes to all API routes.

---

## 8. Monitoring & Observability

### 8.1 Exposed Request IDs
- API responses include `x-request-id` headers (e.g., `9099a6d7b86345b184b2626fe16de5e2`).
- **Note:** Not inherently bad, but ensure these don't leak internal infrastructure details.

### 8.2 Server Version Disclosure
- `Server: nginx/1.27.5` header is present.
- **Risk:** Attackers can target known vulnerabilities in this specific nginx version.
- **Fix:** Remove or obscure the `Server` header in nginx config: `server_tokens off;`

---

## Summary Table

| Category | Issue | Severity |
|----------|-------|----------|
| Security | No HTTPS | **Critical** |
| Security | No API Authentication | **Critical** |
| Security | AI Provider Config Exposed | **High** |
| Security | Internal File Paths Leaked | **High** |
| Security | Missing Security Headers | **High** |
| Security | innerHTML in JS | **Medium** |
| Security | Server Version Disclosed | **Low** |
| Performance | No Compression | **Medium** |
| Performance | No HTTP/2 | **Medium** |
| Performance | No Cache Headers | **Medium** |
| Performance | No Resource Hints | **Low** |
| SEO | Missing OG/Twitter Tags | **Low** |
| SEO | No robots.txt/sitemap | **Low** |
| Accessibility | Empty SPA Shell | **Medium** |
| UX | Broken/Empty Wave Section | **Medium** |
| UX | Persistent Loading States | **Low** |
| Architecture | No API Versioning | **Low** |
| Architecture | No Rate Limiting | **Medium** |

---

## Recommended Priority Order

1. **Enable HTTPS** — Free with Let's Encrypt.
2. **Add Authentication** — Protect all API routes immediately.
3. **Add Security Headers** — CSP, X-Frame-Options, HSTS, etc.
4. **Remove/Protect Internal Endpoints** — `/api/qwen/*` should not be public.
5. **Enable Compression & Caching** — Quick nginx config wins.
6. **Fix Empty/Broken UI States** — Better empty states and loading indicators.
7. **Add SEO Meta Tags** — OG, Twitter, canonical, robots.txt.
8. **Improve Accessibility** — SSR/noscript, skip links, table markup.
