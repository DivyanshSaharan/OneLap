# Increment 12: durable follow-up source references

Increment 11 was approved and pushed as `f511d52`. The user approved committing and pushing this increment on October 10. Its resulting commit is recorded in Git history; this approval does not authorize additional model calls or training.

## One functionality

Accepting a follow-up now saves its generating journal ID and ordered selected entry IDs alongside the mission in the same IndexedDB transaction. The generating owner is captured with the response, not read from a possibly different journal at acceptance time. Those references survive offline reload and are inspectable inside **How this was generated**, together with the actual model target and prompt version. Pocket mode remains minimal.

Only one main source and up to two distinct earlier source IDs are allowed. No note text, timestamps or reflection copies are added to this metadata, and it is not attached to the API mission snapshot or uploaded during journal sync. Opening the details does not contact Atlas/Tinker or verify that a source still exists. References can remain after a source note is deleted; they do not restore that note or prove the model's interpretation is grounded. Local mission storage is not encrypted.

Imported files cannot claim these links. Existing mission-only/imported records and old follow-ups remain readable; older follow-ups clearly say source references were not saved. A new generation/import clears stale links. Clearing the saved mission removes its links, not journal entries. Failed replacement keeps both the previous mission and references intact.

## Verification and live evidence

The separately approved fresh live browser run on `f511d52` passed using real Tinker/Atlas with two fictional samples and verified cleanup. Details and limitations: [live-browser-2026-10-10.md](live-browser-2026-10-10.md). This was before the new local-reference behavior; it is not evidence of that behavior against live services.

The new behavior passes the production-browser fixture loop after deletion/offline reload, without extra hosted requests. The opened source-reference panel also fits a 320-pixel viewport without horizontal overflow; its screenshot was visually inspected. Unit tests cover bounded metadata, corruption, imported/initial-mission rejection, old-save compatibility, owner capture, atomic replacement/failure, clearing stale references and no automatic reads.

Final verification: 182 frontend tests, 386 offline backend tests, five existing production Edge checks, 24 static-handoff tests and nine browser-request boundary tests pass. Type checking, production build, Prettier, Ruff lint/format, dependency checks and Git whitespace checks pass. The fixture uses isolated local doubles and its own ledger; read-only preflight confirms the real ledger remains unchanged and sharing gates are off. These are desktop checks, not a physical-phone test.

Both newly approved hosted requests are used. The real ledger remains six requests / $0.004665 estimated, and saved gates are off. No training, Sentry export, public deployment, physical-phone offline result or actual outing has been performed. Reports and screenshots remain ignored; publication needs approval.
