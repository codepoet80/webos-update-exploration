# CLAUDE.md — "Get Ready for OTA" app + System Updates reroute

Resume-here notes for this sub-project. Read this first.

## What this is

Two on-device pieces that prepare an HP TouchPad for the community OTA and let the
native updater deliver it:

- **Part 1 — "Get Ready for OTA"** (`org.webosarchive.otaready`): an Enyo 1 app that runs
  the OTA-eligibility fingerprint and tells the user whether they're ready, or what to do
  (install the TLS suite, remove a custom kernel…). **Advise-only** (per the user's choice) —
  it shows steps, it does not install/remove anything itself.
- **Part 2 — System Updates reroute**: a patch to the stock **`com.palm.app.updates`** so its
  "Check Now" reads *our* offer and renders it in the native UI, instead of calling the
  carrier-gated `palm://com.palm.update` daemon (which never reaches a server on Wi‑Fi
  TouchPads — proven dead end).

Both are fed by a **root daemon** (`otaready-daemon`) because jailed Enyo apps can't read
system state or write system files.

## Architecture

```
                    /usr/bin/ota-fingerprint --json   (= device-scripts/fingerprint.sh)
                                 │  (run as root by the daemon)
   otaready-daemon (root, upstart)  ─────────►  /media/internal/.otaready/status.json   ← Get Ready app reads (XHR file://)
        │  polls .otaready/cmd                    /media/internal/.otaready/offer.json    ← patched System Updates reads
        │  produces offer.json (test-offer override, or /api/updates/plan translation)
        └─ cmd: check | redirect(apply patch) | revert | install(TODO)
```

- **Data contract** `status.json` = `fingerprint.sh --json`: `{verdict, action, ready, model, L, T, Q, kernel, optware_ssl, patches, reason}`. `action ∈ READY | INSTALL_TLS | REMOVE_KERNEL | REVIEW | UNSUPPORTED`.
- **`offer.json`** is in the native UpdatesApp payload shape: `{status:"Available", version, size, installTime, networkAvailable, priority}` (or `{status:"UpToDate"}`).
- Eligibility comes from `../webos-update-server` (`dm/eligibility.py`, `/api/updates/plan`, `packages/eligibility.json`).

## Status (2026-07-03)

### Working / proven on hardware (Device A)
- **Part 2 display reroute WORKS end-to-end.** Stock System Updates renders our offer:
  *"Installation of webOS Community Update 1.0 will take about 5 minutes"* + **Install Now**,
  with zero contact with Palm's servers. Verified on Device A.
- **Part 1 installs and runs.** postinst installs+starts the daemon; `status.json` is written;
  the app shows the READY state on Device A (baseline A).
- **Part 1 UI/theming FIXED and verified on device (v1.0.3, 2026-07-03).** MainView copies the
  `com.palm.app.dateandtime` first-party idiom: `enyo-toolbar-light header-welcome` header
  (48px `images/header-icon-otaready.png` + title), `Scroller` → 500px `box-center` column of
  captioned `RowGroup`/`Item` groups (Status / What To Do / Device Details label–value rows),
  themed `Spinner`, bottom `Toolbar` with `enyo-button-affirmative` redirect button. Emoji removed
  (2011 WebKit has no color-emoji font); state is a colored bold headline instead. CSS carries only
  dateandtime's layout rules (`box-center`, `header-welcome`, `enyo-group`) + small app classes.
- **Fingerprint `--json`** validated on-device (Device C → `INSTALL_TLS`, Device A → `READY`).

### Broken / incomplete
- **Part 2 Install handoff is a STUB.** `otareadyInstall()` in `UpdatesApp.patched.js` just logs.

## Hard-won on-device lessons (do not relearn these)

1. **Cache-bust = bump the app version.** Swapping an app's JS and restarting Luna is NOT enough —
   webOS serves cached code. You MUST bump `appinfo.json` `version` to force a reload. Confirmed
   repeatedly (System Updates 1.1.0→1.1.1→1.1.2; Get Ready 1.0.0→1.0.1→1.0.2).
2. **Use plain `XMLHttpRequest` + `JSON.parse`, NOT `enyo.xhr`/`enyo.json`.** This Enyo build's
   `enyo.xhr.request(url, opts)` treats the first arg as an options object (`'sync' in <url>`) and
   throws during `create()` → white screen. Both `UpdatesApp.patched.js` and `MainView.js` use raw XHR.
3. **XHTML 1.1 doctype + first-party markup for theming** — verified (v1.0.3). HTML5
   `<!doctype html>` drops 2011 WebKit into a mode where the era's enyo theme CSS doesn't apply,
   AND the theme only styles real Enyo kinds (`RowGroup`/`Item`/`Toolbar`…), not bare divs.
   Copy `com.palm.app.dateandtime` (index.html doctype, header-welcome/box-center layout) exactly.
4. **Load the system enyo:** `/usr/palm/frameworks/enyo/0.10/framework/enyo.js` (0.10, what the
   themed 1p apps use). The bundled-enyo pattern in `~/Desktop/jonwise/Projects/enyo1-bootplate`
   is only for web/Android portability — not needed (or wanted) here.
5. **Headless launch can't force a fresh `create()`** — webOS restores a "Previously-Saved" card,
   so `luna-send .../launch` over novacom re-shows cached state without re-running the app. **Testing
   the UI requires a human to swipe-close + reopen the app.** (novacomd survives Luna restarts.)
6. **`ipkg -o /media/cryptofs/apps install` DEFERS postinst** — run it manually:
   `sh /media/cryptofs/apps/usr/lib/ipkg/info/<pkg>.postinst`. Real Preware/WOSQI installs run it.
7. **A cryptofs app does NOT shadow a `/usr/palm/applications` system app** of the same id — the
   system app wins. So Part 2 patches the rootfs app in place (backup + version bump), not via a
   cryptofs override.
8. **Enyo apps can't write files** — the Part 2 Install trigger (app→daemon) needs a small JS
   service (see TODO); reads are fine via `XMLHttpRequest` to `file://`.

## Build & install

```bash
./build.sh                 # -> org.webosarchive.otaready_<ver>_all.ipk (bump version first!)
# on device (Preware/WOSQI, or for testing:)
#   ipkg -o /media/cryptofs/apps install /media/internal/<ipk>
#   sh /media/cryptofs/apps/usr/lib/ipkg/info/org.webosarchive.otaready.postinst   # run deferred postinst
#   killall LunaSysMgr    # restart to load
```

## Device A current state (leftover from testing — REVERT when done)

- **`com.palm.app.updates` is PATCHED in place** on rootfs: `app/UpdatesApp.js` = our reroute,
  stock saved to `app/UpdatesApp.js.otaready-orig`, `appinfo.json` version bumped to **1.1.2**.
  **To revert:** restore `UpdatesApp.js.otaready-orig` → `UpdatesApp.js`, set version back to `1.1.0`,
  `killall LunaSysMgr`.
- **`org.webosarchive.otaready` v1.0.3 installed**; daemon + `/usr/bin/ota-fingerprint` +
  `/etc/event.d/otaready-daemon` installed; daemon running.
- `/media/internal/.otaready/`: `status.json` (READY), `offer.json` + `test-offer.json` (Available demo).
  The `test-offer.json` is what keeps the demo showing "Available" (baseline A otherwise resolves to UpToDate).

## What's left (TODO, roughly in order)

1. ~~Verify Part 1 theming/UI on device~~ **DONE** — v1.0.3 confirmed looking right on Device A (2026-07-03).
2. **Replace the placeholder icon** (`icon.png` is currently System Updates' icon; the 48px
   `images/header-icon-otaready.png` is scaled from it — regenerate both together).
3. **Build the Install handoff (Part 2):**
   - A small **JS service** in the app package that writes `/media/internal/.otaready/cmd` (Enyo
     can't write files); the patched `otareadyInstall()` calls it.
   - The daemon's **`install`** action = the direct-update flow (download IPKs from our server →
     write `/var/lib/software/SessionFiles/` → `make-update-uimage` → reboot into the OTA ramdisk).
     Reuse `../webos-update-server/device-scripts/direct-update.sh`. On reboot-back, relaunch
     System Updates with `updateSuccessful` (the app already handles that param).
4. **Fix the daemon's `redirect`/`apply_patch`** to ALSO bump `com.palm.app.updates`' version
   (cache-bust) and close the card — right now it only swaps the file, which won't reload.
5. **Real offer content**: `/api/updates/plan → offer.json` translation is best-effort; no OTA
   packages are hosted yet. The **LunaCE launcher update** (worked on elsewhere) is the intended
   real payload; the TLS suite is delivered via Preware, not our OTA.
6. **Wire Part 1 → Part 2**: the "Point me at the new server" button (shown when `ready`) should
   trigger the daemon's `redirect` (needs the JS service from #3).
7. **Revert Device A** to stock when finished (see Device A state above).

## Key references
- 1p apps: `~/Projects/webos-firstparty/` — **dateandtime is the Enyo 1 UI template we copy**
  (deviceinfo and languagepicker are Mojo). Older set: `~/Desktop/jonwise/Projects/com.palm.app.*`.
- Pulled stock System Updates source: `reference/com.palm.app.updates/` (what we patched).
- Fingerprint + eligibility: `../webos-update-server/device-scripts/fingerprint.sh`, `dm/eligibility.py`.
- webOS packaging/services knowledge: the `webos-mcp` resources (`postinst-packaging`, `js-services`, `app-structure`, `gotchas`).
