# Explicit Atlas journal sync

The owner approved journal synchronization on the existing Render service.
`ONELAP_JOURNAL_ENABLED=true` and `ONELAP_ATLAS_SHARING_APPROVED=true` enable the
existing account-scoped journal API. These settings do not enable AI reflections,
change the model allowance or upload existing notes automatically. Google-verified
identity controls journal ownership; no shared owner ID is needed.

## Save and sync

1. Save an observation on this device. It remains in IndexedDB first.
2. Open **Cloud sync & privacy**, then **Check Atlas status**.
3. Review the per-sync consent checkbox. It selects the eligible pending notes
   and deletions belonging to the currently connected account.
4. Choose **Sync pending changes**. Observations, feedback, mission snapshots and
   device timestamps are sent to Atlas; nothing is sent to Tinker.

On another device, sign in with the same Google account, open **Cloud sync &
privacy**, check status and choose **Load cloud journal**. A new mission is not
required. Loading is an explicit read, not an upload or a model request.

Account-bound local notes do not need relinking merely because sync was previously
off. Only older, unassigned device-only notes use the separate review/link flow.
Do not claim another person's notes on a shared browser.

## Boundaries

Sync does not erase local copies. Signing out hides account history rather than
deleting it, and local storage is not encrypted. **Remove observation** removes
local note content and, when applicable, queues a cloud deletion for the next
explicit sync. Clearing browser site data is not cloud deletion.

Saving, signing in, reloading or reconnecting the network does not upload notes.
The server rejects reading, writing or deleting another account's journal. API
and UI tests use synthetic identities; real signed-in production upload/readback
must be verified by the owner. No paid model test or personal-note upload was
performed for this activation.
