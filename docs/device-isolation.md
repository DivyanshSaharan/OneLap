# Device storage by journal identity

Missions, pending notes and follow-up source references are separated by the existing server-provided journal UUID. An explicit connection checks that journal identity before selecting its device cache. Switching journals hides the previous journal's mission, notes and draft; late cloud responses cannot populate the new journal's view. Forgetting the connection returns to a separate device-only scope. The last UUID alone may be remembered for offline access; no access token is persisted.

Legacy device-only observations are not automatically attached to a newly connected journal. The user can explicitly review and link them locally, then separately approve Atlas synchronization. Existing owner-bound observations cannot be rebound to a different journal. Local malformed data fails visibly and blocks upload rather than disappearing silently.

This original increment was cache separation, not authentication or encryption. The later approved Google increment now verifies backend identity and cloud ownership; see [authentication](authentication.md). Device storage is still not encrypted or screen-locked. Anyone with access to the same browser/device storage may inspect it.

Verification includes unit tests for scope changes, stale responses and legacy note recovery, plus an offline browser journal-A/disconnect/journal-B/reload/journal-A scenario. No credentials, live journal contents or hosted model requests are used by these tests.
