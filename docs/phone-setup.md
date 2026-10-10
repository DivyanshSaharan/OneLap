# Private Android field-test setup

For tomorrow's outing: load OneLap over USB once, then unplug and use the saved mission. No public deployment or extra model credit is needed. **This is a procedure, not a successful physical-phone test.**

## Before connecting

Use your own Android phone, a data-capable USB cable and Chrome. USB debugging must be enabled and the phone must approve this computer. Charging, file-transfer mode or Bluetooth pairing alone is not an ADB authorization. See [Android's USB debugging instructions](https://developer.android.com/tools/adb#Enabling).

ADB is part of [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools). It was not found on this machine's PATH or at the usual Android SDK location during preparation. If installed elsewhere, use that actual executable path; otherwise obtain the official Windows package. Do not install an APK, enable wireless debugging or expose ADB on your network for this test.

## Laptop: static preview only

From the OneLap project directory:

```powershell
npm.cmd run build
npm.cmd run handoff
```

Keep that terminal open. The guide is `http://127.0.0.1:4176/handoff`. This command is intentionally different from Vite's development/preview server: it loads only explicit public build files and the public captured JSON, has **no API proxy**, does not read `.env`, and rejects uploads/API routes. Do not start the backend or enable sharing/spending gates for this check.

## Second terminal: map only this port

If `adb.exe` is on PATH:

```powershell
adb.exe devices
adb.exe -d reverse --list
adb.exe -d reverse --no-rebind tcp:4176 tcp:4176
adb.exe -d reverse --list
```

Proceed only when your intended phone shows `device`, not `unauthorized` or `offline`. `-d` selects a USB device and refuses multiple USB devices. For an ADB executable outside PATH, run the same arguments with `& 'C:\actual\platform-tools\adb.exe'`. Do not paste device serials into the public write-up.

`--no-rebind` refuses to overwrite an existing mapping. If 4176 is already mapped, inspect it first; keep an identical mapping or ask before removing a different one. Do not use `--remove-all`. These options are documented in the [official ADB command reference](https://android.googlesource.com/platform/packages/modules/adb/+/refs/heads/main/docs/user/adb.1.md).

On the phone, type **`http://127.0.0.1:4176/handoff`** in Chrome. Keep that exact origin throughout the test; `localhost` is a different browser storage origin. USB reverse maps the phone's local port to the laptop, not a publicly accessible URL. Chrome also documents [USB port forwarding for local servers](https://developer.chrome.com/docs/devtools/remote-debugging/local-server).

## Phone: save, disconnect, check

1. Download the captured JSON from the guide, then tap **Open OneLap**.
2. Expand **Use a captured mission · no model request**, select that downloaded file and read the preview. Its original wording assumes night and particular objects, and its remember line incorrectly describes a proposed choice as already made. Discard it if it does not suit your outing; do not treat it as navigation or a safety assessment.
3. Check the review box and save. Wait for **Saved on this device · ready to reopen offline**. The imported/unverified label must remain visible.
4. Stay on the app's `/` page, unplug USB and disable networking. Reload. Verify the mission, imported label and saved state remain. The guide and download themselves require connection; the service worker deliberately excludes them from app-shell navigation fallback.
5. Tap **I'm heading out**, read once and put the phone away. Skip or stop if unsuitable. The app does not measure your route, duration, other phone use or completion.
6. When back, tap **I'm back — record an observation**, choose the actual outcome/feedback and write one non-identifying observation. **Save observation on this device**, then reload and check it remains. Do not click cloud sync/follow-up in this preview.

If an install shortcut is offered, you may try it, but an offer or successful launch is not proof of offline operation. Ordinary Chrome is enough for the first check. Failure to reopen offline is a result to record, not a reason to claim success or expose a server publicly.

## Cleanup and feedback

Reconnect USB if needed, check the mappings, and remove only the mapping created for this test:

```powershell
adb.exe -d reverse --list
adb.exe -d reverse --remove tcp:4176
```

Stop the handoff terminal with Ctrl+C. Disable USB debugging/revoke this computer's debugging authorization if no longer needed. Keep your saved browser notes unless you want to remove them through OneLap; the test does not clear browser data automatically.

Tell me: did offline reload work, did note reload work, did the mission fit, what did you notice, and was any wording awkward? Add duration or phone interactions only if measured/self-reported; otherwise say **not measured**. No photo, screenshot, exact place, office detail or device serial is needed. The fuller evidence table is in [field-test.md](field-test.md).
