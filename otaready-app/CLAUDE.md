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
        /usr/bin/ota-direct-update  ◄──────────────────┘  cmd: check | redirect(apply patch) | revert | install | reset
                                                          fetches the offer from https://swupdate.webosarchive.org/api/updates/offer
```

- **`org.webosarchive.otaready.service`** (node JS service) is the app→daemon bridge: jailed Enyo
  apps can't write files, so its one public command `trigger {cmd:"check|redirect|revert|install"}`
  writes `.otaready/cmd`. Registered on the Luna bus via LS2 role+service files dropped by postinst
  into `/var/palm/ls2/{roles,services}/{prv,pub}/` (a plain `ipkg install` won't auto-register a
  service). **First install needs one reboot** — ls-hubd caches its role map at boot.

- **Data contract** `status.json` = `fingerprint.sh --json`: `{verdict, action, ready, model, L, T, Q, kernel, optware_ssl, patches, reason}`. `action ∈ READY | INSTALL_TLS | REMOVE_KERNEL | REVIEW | UNSUPPORTED`.
- **`server-state.json`** (daemon → OTA Ready app) drives the app's 3 states for a READY device:
  `{redirected, contacted, serverUrl, lastContact, lastResult}`. `redirected` = System Updates patch
  applied (backup exists). `contacted` = sticky since last re-point (a good server response was seen;
  cleared by redirect/revert). `lastResult` = the offer System Updates shows (Available/UpToDate) so
  both screens agree. States: 1 not-redirected (show re-point button) · 2 redirected+!contacted ·
  3 redirected+contacted (show last check + result).
- **`offer.json`** is in the native UpdatesApp payload shape: `{status:"Available", version, size, installTime, networkAvailable, priority}` (or `{status:"UpToDate"}`).
  **Offer model (v1.1.11):** every *eligible* device gets the same single **server-hosted** offer —
  the daemon `GET`s `/api/updates/offer` (one `offer.json` the server admin edits + git-pushes) and
  serves it verbatim. Eligibility is an **exclusion gate applied on-device**: the daemon only offers
  when the local fingerprint says `ready:true` (a custom kernel / unsupported model / unrecognised
  config → not ready → `UpToDate`, no offer). The OTA is *other* content, not TLS — TLS is only needed
  to reach the server. Local overrides still win for testing: `.installed` → `UpToDate` (payload
  delivered this cycle; `rm` or a fresh `redirect` re-arms), `test-offer.json` → forced demo offer.
- Eligibility comes from `../webos-update-server` (`dm/eligibility.py`, `/api/updates/plan`, `packages/eligibility.json`).

## Status (2026-07-03) — BETA IS LIVE

**End-to-end validated on a fresh device via the real Museum path (device E, 2026-07-03).**
The whole chain works for actual users now: **install "OTA Ready" from App Museum II (Preware) →
postinst sets up the daemon + bridge service → app reads status → "Use New Update Server" patches
System Updates → the server-hosted offer flows in → Install**. This is the graduation from
"proven-via-luna-send on Device A" to "works on hardware through the distribution users will use."

- **Production server is live**: `https://swupdate.webosarchive.org` (FastAPI on the user's host,
  `systemctl` service, git-to-deploy, valid TLS). Serves the single canonical offer at
  `/api/updates/offer` from `offer.json` (edit + git push to change what all devices are offered).
- **App is published to App Museum II** as **"OTA Ready"** (self-update check keys off that exact
  name). Museum candidate build: **v1.1.11**.
- **Confirm next session:** whether the *armed flash* (`arm-install` → reboot into OTA ramdisk →
  install → reboot-back) actually ran in the device-E e2e, or if e2e went through the offer/prepare
  stage. That's the one step never separately confirmed on hardware. (User said "all went well" but
  didn't break down the armed-flash detail.)

### Earlier milestones proven on Device A
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

### Remaining / to confirm
- **Armed flash on hardware** — confirm/record whether the real `arm-install` flash completed in the
  device-E e2e (see status banner). It's the only step never separately verified on hardware.
- **No real OTA payload yet.** The server hosts *test* packages (`updatetest`, `updatefsinfo`) +
  the openssl `.off`. The offer content is a placeholder ("webOS Community OTA Test 0.1"). The
  intended real payload is the **LunaCE launcher update**. Before broad release, know exactly what the
  flashed packages do to the rootfs.
- **"Forgot to reboot" UX** (user flagged as a real beta hazard): after a first Museum install the app
  shows status fine, but the first *action* ("Use New Update Server", Install, Reset, Save) fails with
  "Couldn't reach the OTA Ready helper service… reboot once" until the one-time reboot (see lesson #11).
  Worth making that clearer / prompting the reboot.
- **No user-facing `revert`.** The daemon can un-patch System Updates (`revert` cmd) but there's no
  button; a stuck tester has no exit but Doctor. Consider exposing it or documenting it.

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
11. **App Museum II (Preware) DOES run our postinst** — VERIFIED on hardware. Installing "OTA Ready"
   from the Museum sets up the daemon + helpers + LS2 files exactly like a manual postinst run. The
   **first-install reboot is only for the bridge service**: State 1 (status display, offer viewing) is
   pure file-reading and works immediately; the first thing that *calls* the service (redirect / install /
   reset / save) fails until one reboot registers it with ls-hubd. One-time; survives upgrades+reboots after.
12. **The OTA delivers OTHER content, NOT TLS 1.3.** (Corrected mid-session — don't re-derive the wrong
   model.) Eligibility is an **exclusion gate**, not per-baseline delivery: every device gets the same
   single offer UNLESS its fingerprint rules it out (`ready:false` = custom kernel / unsupported model /
   unrecognised config). TLS matters only because a no-TLS device can't reach the HTTPS server AND is
   `ready:false` anyway. The offer is **server-hosted** (`GET /api/updates/offer`, one `offer.json` the
   admin git-pushes); the daemon serves it verbatim, gated locally by the fingerprint.
13. **Ship the PRODUCTION server default.** The daemon's `SERVER_DEFAULT` was a dead LAN IP
   (`192.168.10.20:8080`) for ages; a fresh Museum device couldn't reach anything → stuck State 2 +
   UpToDate. It's now `https://swupdate.webosarchive.org`. A `/media/internal/.otaready/server-url`
   file still overrides it per-device (for LAN dev). Local `test-offer.json` also overrides the server
   offer — handy for demos, but it MASKS the real server path, so remove it to test end-to-end.

## Build & install

```bash
./build.sh                 # -> org.webosarchive.otaready_<ver>_all.ipk (bump version first!)
# on device (Preware/WOSQI, or for testing:)
#   ipkg -o /media/cryptofs/apps install /media/internal/<ipk>
#   sh /media/cryptofs/apps/usr/lib/ipkg/info/org.webosarchive.otaready.postinst   # run deferred postinst
#   killall LunaSysMgr    # restart to load (app JS)
#   reboot                # ONLY on the FIRST install of the bridge service (ls-hubd role cache; see lesson #9)
```

## The update server (`../webos-update-server`, FastAPI)

**Production is live** at `https://swupdate.webosarchive.org` (user's host, `systemctl` service,
git-to-deploy → whatever we commit reaches it). Matches Palm's old `omadm.swupdate.palm.com` label.
Config is a file, not env vars: `otaserver.conf` (searched `/etc/` then repo; see `DEPLOY.md`).

- **Change the offer for everyone:** edit `offer.json` (one file), git push. `/api/updates/offer`
  reads it per-request (no restart needed). `{"status":"UpToDate"}` withdraws it.
- **Health/monitoring:** `GET /health` (liveness), `GET /api/stats` (per-device traffic: build,
  baseline, checks, downloads, last-seen). Both are unauthenticated — allowlist if that matters.
- **Endpoints the daemon uses:** `/api/updates/offer` (the offer), `/api/updates/check?build=` +
  `/packages/*` (the direct-update install flow). `/api/updates/plan?baseline=` still exists
  (eligibility) but the daemon no longer uses it for the offer.

Run it locally for LAN dev (this box has no pip/venv → bootstrap into scratchpad):
```bash
python3 -m venv --without-pip <venv>
curl -sS https://bootstrap.pypa.io/get-pip.py | <venv>/bin/python
<venv>/bin/pip install -r ../webos-update-server/requirements.txt
cd ../webos-update-server && <venv>/bin/uvicorn server:app --host 0.0.0.0 --port 8080
```
Point a device at the LAN instance by writing its URL into `/media/internal/.otaready/server-url`
(overrides the production default). `config.py` auto-detects the LAN IP when `[public] host` is blank.

## The app (v1.1.11, "OTA Ready (Beta)"; App Museum name "OTA Ready")

- **3-state model** for a READY device (from `server-state.json`): 1 not-redirected (show "Use New
  Update Server") · 2 redirected/awaiting-server · 3 redirected+contacted (last check + result).
- **App Menu** (swipe top-left): **Reset OTA Test** (`reset` → daemon rm `.installed`, re-arm offer),
  **Save Device Details** (`saveDetails` → copies `diagnostics.txt` to `/media/internal/OTAReady-DeviceDetails.txt`
  + `enyo.windows.addBannerMessage`, for users without email), **Send Device Details** (emails
  curator@webosarchive.org via com.palm.app.email). No "Check for Updates" item — see next.
- **Self-update on launch:** `source/Updater-Helper.js` (`Helpers.Updater`, from webOSArchive/webos-common)
  checks `appcatalog.webosarchive.org` with name **"OTA Ready"** vs installed `#.#.#`; if newer, pops
  "Update Now / Later" → installs via Preware. Silent until published; existing testers self-update.
- **Patched System Updates** (`UpdatesApp.patched.js`, applied by `redirect`): reads `offer.json`, has
  the "undefined minutes" fix + the deliver→UpToDate lifecycle (`.installed` marker → "no more updates").
- **Icon:** `tools/make_icon.py` renders 3 sizes (48/64/256) — gift (from `updates.png`, platform
  auto-removed) over a green arrow on a glossy circle.

## Test-device leftover state to clean up (REVERT when done)

- **Device A** (`c931ddf8…`): `com.palm.app.updates` still **PATCHED in place** (our reroute; stock
  saved as `UpdatesApp.js.otaready-orig` + `appinfo.json.otaready-orig`). Revert: daemon `revert` cmd
  (restores both from backups + Luna restart), or restore manually. Old app builds installed.
- **Museum-test device** (`e516be7b…`, baseline B): freshly cleaned then re-installed 1.1.11 from the
  Museum; leftover local `test-offer.json`/`server-url` were removed so it fetches the real server offer.
- **Device E**: the e2e success device (fresh Museum install → full flow).
- Local overrides that mask the real server, if present on any device: `/media/internal/.otaready/`
  `test-offer.json` (forces a demo offer), `server-url` (points elsewhere), `.installed` (→ UpToDate),
  `arm-install` (arms the real flash). Remove to test the true production path.

## The plan (what's left, roughly in order)

**Done** (this run): theming · 3-size icon · JS bridge service + install handoff · redirect
cache-bust · confirmation dialog · server-hosted offer + on-device eligibility gate · App Menu
(reset/save/send) · self-update check · health/stats + `otaserver.conf` + `DEPLOY.md` · production
deploy to `swupdate.webosarchive.org` · publish to App Museum II · **fresh-device e2e via Museum (device E)**.

**Next:**
1. **Confirm + record the armed flash.** Did device E's e2e actually flash (`arm-install` → OTA
   ramdisk → install → reboot-back), or stop at prepare? It's the last hardware-unverified step.
2. **Host the real payload.** Swap the test packages (`updatetest`/`updatefsinfo`) for the intended
   **LunaCE launcher update**; know exactly what the flashed IPKs do to the rootfs before arming on
   testers' devices. Update `offer.json` version/size to match.
3. **Broaden the beta** once #1/#2 are solid — more testers via the Museum. They self-update as you
   publish new builds.
4. **Beta UX polish:** (a) the "forgot to reboot" case — prompt/guide the one-time reboot after first
   install; (b) expose or document a user-facing `revert` (un-patch System Updates) so a stuck tester
   has an exit besides Doctor.
5. **Server:** allowlist/basic-auth `/api/stats` + `/health` if the client-IP exposure matters.
6. **Cleanup:** revert Device A's patched System Updates to stock (daemon `revert`), and clear leftover
   `.otaready/` override files on old test devices (see the test-device list above).

## Key references
- **Production server:** `https://swupdate.webosarchive.org` (git-to-deploy from `../webos-update-server`).
  Offer = `offer.json` served at `/api/updates/offer`; deploy/config in `../webos-update-server/DEPLOY.md`
  + `otaserver.conf`. Palm's original host was `omadm.swupdate.palm.com` (found in device `DmTree.xml`).
- **App Museum II:** app published as **"OTA Ready"** (self-update name must match exactly). Museum
  installs via Preware → runs our postinst. Updater lib synced from `github.com/webOSArchive/webos-common`.
- 1p apps: `~/Projects/webos-firstparty/` — **dateandtime is the Enyo 1 UI template we copy**
  (deviceinfo and languagepicker are Mojo). Older set: `~/Desktop/jonwise/Projects/com.palm.app.*`.
- Pulled stock System Updates source: `reference/com.palm.app.updates/` (what we patched).
- Fingerprint + eligibility: `../webos-update-server/device-scripts/fingerprint.sh`, `dm/eligibility.py`.
- webOS packaging/services knowledge: the `webos-mcp` resources (`postinst-packaging`, `js-services`,
  `ls2-roles`, `app-structure`, `gotchas`).
- JS-service reference (ground truth for this build): the shipping `com.quickoffice.webos.service`
  on Device A (`/media/cryptofs/apps/usr/palm/services/…`) — a node/fs service we copied structure from.
