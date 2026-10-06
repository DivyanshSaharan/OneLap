# Atlas setup — keep sync disabled for now

This guide is for the owner to follow in their own account. An authenticated, read-only Atlas ping passed on October 6, 2026. **Journal writes, reads and deletion have not been tested live.** Do not paste credentials into chat. Setup is not authorization to upload notes.

## 1. Create a free cluster

Sign in to MongoDB Atlas, create a OneLap project, then create a cluster using the explicitly labelled **Free / M0** option. Do not select Flex, dedicated tiers or paid upgrades. Check the displayed price before proceeding. Select an available provider/region without publishing it alongside private whereabouts. Atlas allows one Free cluster per project. [Official Free cluster guide](https://www.mongodb.com/docs/atlas/tutorial/deploy-free-tier-cluster/).

Create a dedicated database user with a strong password and `readWrite` privileges scoped to the `onelap` database only. Restrict it to this cluster where available. Do not use an administrator or all-databases role. Database credentials are distinct from your Atlas account login. [Official database-user guide](https://www.mongodb.com/docs/atlas/security-add-mongodb-users/).

Add **your current public IP only** to the project's network access list. Do not enable access from anywhere (`0.0.0.0/0`). If your IP changes, update that entry. Future hosting needs a separate review of the host's outbound addresses. [Official IP access-list guide](https://www.mongodb.com/docs/atlas/security/ip-access-list/).

## 2. Configure secrets locally

Use the cluster's connection dialog for a Python driver and copy its `mongodb+srv://` connection string. Replace credential placeholders privately; reserved characters in a password must be URL-encoded. Keep TLS verification enabled. Never put this URI in a browser variable, screenshot, commit or message.

If not already present, create an ignored root `.env` from `.env.example`. Do not overwrite an existing `.env`. Install the journal dependencies from the project directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-journal.txt
```

**No owner ID or access token setup is required for local use.** OneLap supplies a stable personal journal ID automatically. With `ONELAP_ACCESS_TOKEN` unset/empty, the backend accepts only loopback development requests with approved localhost host/origin metadata and no forwarding headers. Keep the API bound to `127.0.0.1`, and do not publish or tunnel this mode. This is one shared personal journal, not a user-account system.

Edit these values **only in your local `.env`**, replacing placeholders:

```dotenv
MONGODB_URI=your-private-atlas-srv-uri
ONELAP_MONGODB_DATABASE=onelap
ONELAP_JOURNAL_ENABLED=false
ONELAP_ATLAS_SHARING_APPROVED=false

ONELAP_HOSTED_REQUESTS_ENABLED=false
ONELAP_DATA_SHARING_APPROVED=false
ONELAP_APPROVED_BUDGET_USD=0
```

Environment variables override `.env`; settings are read at server startup. Leave both journal gates **false** throughout setup. In the app, open **Backend connection → Connect to local backend**; no token entry is needed. Status checks do not connect to MongoDB, and installing dependencies does not upload notes.

For a future non-local deployment, configure a private `ONELAP_ACCESS_TOKEN` and use the optional protected-server connection form. Setting a token restores mandatory bearer authentication with no local bypass. `ONELAP_OWNER_ID` remains an optional advanced override for an existing separate journal; changing it does not migrate records.

Atlas's IP allowlist is separate from application access. Allowing every IP does not replace database credentials or protect the app API. Prefer narrowing it to the required client addresses after testing. OneLap does not edit your Atlas network settings. [Official IP access-list guide](https://www.mongodb.com/docs/atlas/security/ip-access-list/).

## 3. Stop at the live-test approval boundary

Tell me **“Atlas configured; sync still disabled.”** Do not send the URI, password or access token. Before enabling either journal flag, explicitly approve a fictional write/read/delete test.

That test sends an observation, feedback, mission snapshot and device timestamp to Atlas. It does not send them to Tinker. We will keep AI gates off, enable journal gates only for the approved test, restart the API and use the app's explicit sync controls. An enabled configuration status is not proof of connectivity; the write/read/delete checks provide that evidence.

Deletion removes note content from the active collection but keeps an ID/owner tombstone to prevent delayed retries restoring it. Provider backups may retain earlier content. Do not test with real private observations first, and do not promise immediate erasure everywhere.

If connection fails, check the allowed IP, database-scoped permissions and privately configured URI. Do not turn off TLS verification or broaden access to every IP. Report only OneLap's redacted error code.
