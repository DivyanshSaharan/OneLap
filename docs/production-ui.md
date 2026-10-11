# Mission-first interface

The initial screen shows preparation and the mission/pocket experience, not an empty journal or a developer checklist. Returning with a mission or existing notes reveals the journal. Cloud sync/privacy and the next-outing model controls are separate collapsed sections; opening them alone makes no request. Saving a note stays local, sync consent stays per operation, and AI follow-up keeps its separate reviewed-data consent.

The captured-file utility follows the journal rather than interrupting the main loop. Connection details and provenance remain expandable. User-facing offline messages describe what can reopen rather than service-worker internals; development caching limitations are still stated honestly. Account login is not implemented, so the existing private/local connection controls remain until the separately excluded Google-authentication increment.

Verification on October 11: 200 frontend unit tests; six Edge production-browser checks; TypeScript and production build; the seven-stage packaged-server fixture workflow with verified cleanup; 24 public-file/handoff and nine request-boundary tests. Responsive preparation and collapsed journal screenshots were inspected. Checks use disposable profiles and fictional data, not the user's personal journal or physical phone. No paid requests are made by this UI increment.
