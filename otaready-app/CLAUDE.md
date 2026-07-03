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
   Get Ready app ─┐                        ┌─► status.json     (Get Ready reads, XHR file://)
   System Updates ─┤ palm://…otaready.service/trigger {cmd}    ├─► offer.json      (patched System Updates reads)
                   ▼  (JS service writes .otaready/cmd)         ├─► install-status.json (System Updates polls during install)
   org.webosarchive.otaready.service  ──writes cmd──►  otaready-daemon (root, upstart)
                                                        │  polls .otaready/cmd every 1s
        /usr/bin/ota-fingerprint --json ◄──────────────┤  runs as root:
        /usr/bin/ota-direct-update  ◄──────────────────┘  cmd: check | redirect(apply patch) | revert | install
```

- **`org.webosarchive.otaready.service`** (node JS service) is the app→daemon bridge: jailed Enyo
  apps can't write files, so its one public command `trigger {cmd:"check|redirect|revert|install"}`
  writes `.otaready/cmd`. Registered on the Luna bus via LS2 role+service files dropped by postinst
  into `/var/palm/ls2/{roles,services}/{prv,pub}/` (a plain `ipkg install` won't auto-register a
  service). **First install needs one reboot** — ls-hubd caches its role map at boot.

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
- **Part 2 Install handoff WORKS end-to-end (v1.1.0, verified on Device A 2026-07-03).** The
  `org.webosarchive.otaready.service` JS bridge, the daemon's `install` action, and the
  `install-status.json` feedback channel are all proven via luna-send:
  `trigger{cmd:install}` → service writes `.otaready/cmd` → daemon runs `do_install` (direct-update
  prep) → writes `install-status.json`. Safe: the irreversible flash+reboot only runs if
  `.otaready/arm-install` exists (absent by default), so testing never touches the OTA ramdisk.
  With no packages hosted the daemon correctly reports `{"status":"uptodate"}`.

- **Redirect UX fixed (v1.1.1):** "Use New Update Server" now shows a confirmation Dialog first
  ("the screen goes dark for several seconds and open apps close — expected, not a crash"), because
  the redirect deliberately restarts Luna to reload the patched System Updates app. The abrupt
  restart with no warning previously read as a crash.

### Broken / incomplete
- **UI buttons not yet human-verified.** The plumbing (bridge service, daemon actions, cache-bust)
  is all proven via luna-send, but the two on-device buttons still need a swipe-close+reopen test
  (lesson #5): Get Ready's "Use New Update Server" (dialog → `redirect`) and System Updates'
  "Install Now" (`otareadyInstall()` → `install`). With TODO #4 fixed, System Updates should now
  load the patched code after a redirect.

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
8. **Enyo apps can't write files** — the Part 2 Install trigger (app→daemon) goes through the
   `org.webosarchive.otaready.service` JS service, which writes `.otaready/cmd`; reads are fine via
   `XMLHttpRequest` to `file://`.
9. **A manually-`ipkg`-installed JS service is NOT registered on the Luna bus** — the real
   installer generates the LS2 role+service files; our postinst does it by hand (copied the
   exact format from the shipping `com.quickoffice.webos.service`: role `exeName:"js"`,
   type `regular`; bus file `Exec=/usr/bin/run-js-service -n <svc-dir>`; both dropped in
   `/var/palm/ls2/{roles,services}/{prv,pub}/`). **ls-hubd caches roles at boot → first install
   needs a reboot** (not just `killall LunaSysMgr`); later app upgrades reuse the same files, no reboot.
10. **On-demand JS services cold-start in ~1-2s** — a foreground `luna-send` can race and look like
   a silent failure (no response printed over novacom either — that's cosmetic). The app-side
   PalmService is async (onSuccess/onFailure) so it waits correctly. To test from a shell, background
   the call and give it a few seconds; confirm via `/var/log/messages` (service `console.log`s land there).

## Build & install

```bash
./build.sh                 # -> org.webosarchive.otaready_<ver>_all.ipk (bump version first!)
# on device (Preware/WOSQI, or for testing:)
#   ipkg -o /media/cryptofs/apps install /media/internal/<ipk>
#   sh /media/cryptofs/apps/usr/lib/ipkg/info/org.webosarchive.otaready.postinst   # run deferred postinst
#   killall LunaSysMgr    # restart to load (app JS)
#   reboot                # ONLY on the FIRST install of the bridge service (ls-hubd role cache; see lesson #9)
```

## Running the update server locally (there is no prod server — we ARE it)

The daemon/app talk to `../webos-update-server` (FastAPI). To run it on this dev box:

```bash
# one-time: this host has no pip/venv, so bootstrap into scratchpad
python3 -m venv --without-pip <venv>
curl -sS https://bootstrap.pypa.io/get-pip.py | <venv>/bin/python
<venv>/bin/pip install -r ../webos-update-server/requirements.txt
# run (binds 0.0.0.0:8080; access log shows each device request):
cd ../webos-update-server && <venv>/bin/uvicorn server:app --host 0.0.0.0 --port 8080
```

- `config.py` `SERVER_URL` now **auto-detects this host's LAN IP** (was hardcoded to .20) so the
  download URLs it hands the device are reachable; override with the `SERVER_URL` env var.
- Point a device at it: write the URL into `/media/internal/.otaready/server-url` on the device
  (this dev host was `192.168.10.45`, the TouchPad was `192.168.10.41` — both may change via DHCP).
- Endpoints exercised: `/api/updates/plan?baseline=<X>` (daemon offer check),
  `/api/updates/check` + `/urls` + `/session-files` (direct-update/install flow).

## Device A current state (leftover from testing — REVERT when done)

- **`com.palm.app.updates` is PATCHED in place** on rootfs: `app/UpdatesApp.js` = our reroute,
  stock JS saved to `app/UpdatesApp.js.otaready-orig`, stock appinfo saved to
  `appinfo.json.otaready-orig` (captured at **1.1.2**, since the manual bump predates the backup;
  true stock is 1.1.0). `appinfo.json` version now climbs +1 per redirect (currently **1.1.3**).
  **To revert:** run the daemon's `revert` (restores JS + appinfo from the `.otaready-orig` backups),
  or manually restore both `.otaready-orig` files and `killall LunaSysMgr`.
- **`org.webosarchive.otaready` v1.1.1 installed** (titled "OTA Ready"); daemon + `/usr/bin/ota-fingerprint`
  + `/usr/bin/ota-direct-update` + `/etc/event.d/otaready-daemon` installed; daemon running.
- **Bridge service registered**: `org.webosarchive.otaready.service` on the Luna bus (LS2 files in
  `/var/palm/ls2/{roles,services}/{prv,pub}/`). Device A was **rebooted once** on 2026-07-03 to load it.
- **App is v1.1.2 on device; daemon is the v1.1.3 fix** (pushed straight to `/usr/bin/otaready-daemon`
  during live testing — app JS is unchanged between the two, so a full 1.1.3 reinstall is cosmetic).
- **Now pointed at the LOCAL live server**, not the forced demo:
  - `/media/internal/.otaready/server-url` = `http://192.168.10.45:8080` (override; daemon default is still .20).
  - `test-offer.json` renamed to `test-offer.json.bak` (the forced-Available demo is DISABLED so
    make_offer calls the live server). `offer.json` now = live result = `{"status":"UpToDate"}` (correct for baseline A).
  - **To restore the forced-Available UI demo:** `mv test-offer.json.bak test-offer.json` (and optionally
    `rm server-url` to go back to the .20 default).
- `install-status.json` = `{"status":"uptodate"}` left from the handoff test (harmless).

## What's left (TODO, roughly in order)

1. ~~Verify Part 1 theming/UI on device~~ **DONE** — v1.0.3 confirmed looking right on Device A (2026-07-03).
2. ~~Replace the placeholder icon~~ **DONE** (v1.0.4) — custom webOS-style glossy-circle icon
   (broadcast arcs + green download arrow); 64px launcher + 48px header both rendered from the
   generator script (`tools/make_icon.py`, run from the app root; redraws at 512px and downscales). App renamed
   to **"OTA Ready"** (appinfo title, in-app header, html title).
3. ~~Build the Install handoff (Part 2)~~ **DONE** (v1.1.0, plumbing verified via luna-send) —
   JS bridge service + daemon `install`/`do_install` (direct-update prep, `arm-install`-gated
   flash) + `install-status.json` feedback. Patched `otareadyInstall()` calls the service and polls
   status. On reboot-back the app still handles `updateSuccessful`. STILL TODO here: (a) human UI
   test of the "Install Now" button (needs #4 so the new patched code actually loads); (b) real
   armed flash once packages are hosted (#5).
4. ~~Fix the daemon's `redirect`/`apply_patch` to cache-bust~~ **DONE** (v1.1.1, verified on
   Device A 2026-07-03) — `apply_patch` now backs up + bumps `com.palm.app.updates`' appinfo
   version by +1 on every apply (`bump_su_version`), so the Luna restart actually drops the cached
   `UpdatesApp.js` and loads the patched code. Verified: SU version 1.1.2 → 1.1.3 on redirect.
   `revert_patch` restores the stock appinfo from its backup too. The redirect also now waits 2s so
   the app can show its "screen will reload" notice before Luna restarts.
5. **Real offer content**: the `/api/updates/plan → offer.json` translation now works (fixed in
   v1.1.3 — the old check looked for a `"hosted"` field the /plan response never emits, so it
   always fell through to UpToDate; now it keys on a non-empty `"deliver":[{…` array). **Verified
   live 2026-07-03**: baseline A→UpToDate (device has everything), baseline C/D→Available
   "Community TLS 1.3 stack". Still TODO: no *real* OTA package payloads are hosted (the packages
   dir has test ipks + the openssl `.off`); size/installTime in the offer are still hardcoded (the
   /plan response carries no size). The **LunaCE launcher update** is the intended real payload.
6. ~~Wire Part 1 → Part 2~~ **DONE** (v1.1.0) — Get Ready's "Use New Update Server" button calls
   the bridge service with `redirect`. Needs the same human swipe-close+reopen UI test.
7. **Revert Device A** to stock when finished (see Device A state above) — now also: remove the
   bridge-service LS2 files (`prerm` does this) and reboot.

## Key references
- 1p apps: `~/Projects/webos-firstparty/` — **dateandtime is the Enyo 1 UI template we copy**
  (deviceinfo and languagepicker are Mojo). Older set: `~/Desktop/jonwise/Projects/com.palm.app.*`.
- Pulled stock System Updates source: `reference/com.palm.app.updates/` (what we patched).
- Fingerprint + eligibility: `../webos-update-server/device-scripts/fingerprint.sh`, `dm/eligibility.py`.
- webOS packaging/services knowledge: the `webos-mcp` resources (`postinst-packaging`, `js-services`,
  `ls2-roles`, `app-structure`, `gotchas`).
- JS-service reference (ground truth for this build): the shipping `com.quickoffice.webos.service`
  on Device A (`/media/cryptofs/apps/usr/palm/services/…`) — a node/fs service we copied structure from.
