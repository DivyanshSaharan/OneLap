# Google sign-in and separate journals

The owner approved this increment on October 11, replacing the earlier authentication exclusion. Google Identity Services provides popup sign-in, followed by backend ID-token verification and an opaque OneLap session. No redirect URI, Gmail/Drive access or OAuth code exchange is used.

## Local setup

Keep these values in the ignored root `.env`:

```dotenv
GOOGLE_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-private-client-secret
MONGODB_URI=your-authenticated-Atlas-SRV-URI
ONELAP_AUTH_ORIGINS=http://localhost:4174,http://localhost:5174,http://localhost:8770
```

Open `http://localhost:4174` for the production preview or `http://localhost:5174` for development. Google requires approved browser origins; `127.0.0.1` and a LAN IP are not substitutes for the configured localhost origins. Vite proxies `/api` to the loopback backend on port 8770. For a phone outside the laptop network, deploy to the actual Render HTTPS origin and add that exact origin both here and in Google's Authorized JavaScript origins. Deployment is not performed by this increment.

Use Google's basic sign-in permissions only. The Authorized redirect URIs list stays empty for the JavaScript popup callback. Basic sign-in is exempt from Google's Testing audience/test-user restrictions and seven-day authorization expiry; Testing mode is **not** an application allowlist. Branding/domain verification may have separate requirements when publishing. See [Google audience rules](https://support.google.com/cloud/answer/15549945?hl=en).

The Client ID is public configuration; the Client Secret never enters the frontend. No secret is needed to verify Google's signature. To avoid another setup credential, the existing private secret signs domain-separated, short-lived OneLap login challenges. Rotating it invalidates pending challenges, not existing opaque sessions. Keep it secret and never prefix it with `VITE_`.

When a Client ID is configured, every protected API requires a valid Google-derived session. Neither the legacy bearer token nor token-free localhost access can bypass this. The production UI now requires verified sign-in before mounting any mission, import or journal controls. Unknown identity, unavailable authentication and failed session checks stay locked; there is no anonymous UI fallback. Backend-only legacy development boundaries are not multi-user authentication and cannot unlock this UI.

An already verified, open tab can read its saved mission and record local notes offline. A fresh reload, including an offline reload, must verify the session again before exposing the workspace. Keep the signed-in tab open when heading outside. Logout locks and unmounts the workspace immediately, even while revocation is pending or fails; retained session metadata only allows retrying sign-out. Local data is not deleted or encrypted by this gate.

## What is verified and stored

- Google's Python library verifies signature, audience, issuer and expiry. The backend additionally matches the browser's fresh nonce. Tokens are never decoded-only or trusted because the frontend says login succeeded. [Google verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).
- A signed five-minute HttpOnly challenge cookie binds login to this browser. A matching CSRF value and exact allowed Origin/Host are required. The unique consumed-challenge document prevents concurrent/repeated login replay.
- The backend derives a canonical journal UUID from verified Google `sub`, not a supplied owner ID, email or name. Existing personal-journal records are **not migrated or assigned to the first account**.
- `auth_sessions` is separate from `outings` and the global spending collection. It stores hashed opaque session IDs, journal UUIDs, CSRF values and expiry dates, plus short-lived used-challenge IDs. No names, emails, Google subjects or ID tokens are persisted. Authentication necessarily shares this minimal metadata with Atlas even when note synchronization is disabled.
- Sessions last at most 24 hours, survive backend restarts and are revoked server-side on logout. MongoDB's TTL index removes expired session/challenge metadata eventually; authorization checks expiry immediately rather than trusting TTL cleanup timing. Requests fail closed on a storage outage. Lost replies are not automatically retried.
- Cookies are HttpOnly, SameSite=Strict, host-only and Secure on configured HTTPS origins. Only the CSRF value is held in JavaScript memory. Mutations require a matching CSRF header and exact allowed Origin. Authentication/status responses are no-store; the service worker never caches `/api/` requests or Google's script.
- Browser storage remains account-scoped but **not encrypted**. Offline reopening intentionally remembers the last journal on that device. Sign-out hides it and returns to the device-only area, without deleting its saved data. Anyone with developer tools/device access can inspect local notes; do not use a shared browser for private observations.

Sign-in checks/restores account and model/journal availability only. It never generates a mission, reads cloud notes, synchronizes pending changes, enables spending/sharing gates or migrates unassigned device notes. The existing explicit per-action consent remains necessary. All accounts share the same global spending limit; a new account does not reset reservations.

## Verification and remaining manual check

Offline backend tests exercise Google's real RSA verifier with locally signed fictional tokens, nonce/audience/issuer/expiry failures, origin/CSRF checks, replay prevention, session restart/revocation, cookie attributes, storage failure and two-account read/write/delete/follow-up isolation. Frontend and production-browser tests use clearly labelled Google/API doubles: they exercise restoration, stale replies, sign-out, StrictMode and account-scoped local notes without making a real Google/Atlas/Tinker request.

The owner reports that real Google login and logout work locally. A second real account and independent live session persistence/revocation checks remain pending. No production deployment or personal-note upload is claimed. Leave model and note-sharing gates off while checking reload/sign-out. On a failed sign-out, the UI locks but honestly reports that remote revocation is unconfirmed; reconnect and retry instead of assuming the cookie was revoked.

Completed verification: 524 backend tests (30 new auth cases), 229 frontend tests, seven Edge production-browser checks, 24 handoff and ten browser-boundary tests, the seven-stage packaged-server fixture workflow with verified cleanup, lint/format, typecheck/build and dependency checks. The browser-login fixture uses an HttpOnly synthetic session and verifies account restoration, local-note separation and zero unapproved uploads. Phone-width sign-in/restored-account screenshots were inspected. No hosted model sample was made by this increment.

Mandatory-gate follow-up verification: 237 frontend tests, seven updated Edge checks and all 30 backend auth cases pass, together with format/typecheck/build. Tests cover unknown/unavailable identity, cached-owner non-authority, pending/failed logout, offline invalidation and locked offline reload. Earlier anonymous static demo and legacy-token packaged browser scripts predate this gate; they cannot unlock the current UI. Their historical success is not a current mandatory-auth workflow claim.
