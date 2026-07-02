# Get Ready for OTA

Two on-device pieces that prepare an HP TouchPad (Topaz, webOS 3.0.5) for the community OTA
and let the **native** updater deliver it.

1. **"Get Ready for OTA" app** — runs the OTA-eligibility fingerprint and tells the user whether
   they're ready, or what to do (install the TLS suite, remove a custom kernel…). Advise-only.
2. **System Updates reroute** — patches the stock `com.palm.app.updates` so its "Check Now" shows
   **our** update in the native UI, instead of the dead, carrier-gated Palm OMA-DM path.

Both are fed by a small **root daemon** that runs the fingerprint and talks to our update server,
because jailed Enyo apps can't read system state or write system files.

## Status

- **System Updates reroute: working end-to-end** on hardware — the stock updater renders our
  offer ("webOS Community Update … Install Now") with no contact with Palm's servers.
- **Get Ready app: installs and runs**, shows the correct readiness verdict — **but its Enyo UI
  theming is not yet right** (controls render unstyled; a doctype fix is in and untested).
- **Install button handoff is stubbed** (the app→daemon trigger + the actual OTA install flow).

See **CLAUDE.md** for architecture, the hard-won on-device lessons, current Device A state, and the
full TODO list. This README is the short version.

## Layout

```
otaready-app/
├── org.webosarchive.otaready/         # the Enyo 1 app
│   ├── appinfo.json  index.html  depends.js  icon.png
│   ├── source/MainView.js            # Part 1 UI (reads status.json); uses XMLHttpRequest, not enyo.xhr
│   ├── stylesheets/otaready.css
│   └── device/                       # installed to system by postinst
│       ├── ota-fingerprint           # generated from ../webos-update-server/.../fingerprint.sh
│       ├── otaready-daemon           # root daemon: status.json + offer.json + cmd handling
│       ├── otaready-daemon.conf      # upstart job
│       └── UpdatesApp.patched.js     # Part 2: the rerouted com.palm.app.updates controller
├── control/{postinst,prerm}          # run as root; install/remove the daemon + helper
├── reference/com.palm.app.updates/   # pulled stock System Updates source (what we patch)
├── build.sh                          # hand-builds the ipk (bump the version first — cache-bust!)
└── CLAUDE.md                         # dev/resume notes
```

## Build & install

```bash
./build.sh     # -> org.webosarchive.otaready_<version>_all.ipk   (bump appinfo.json version first)
```
Install via **Preware** or **WebOS Quick Install** (NOT `palm-install` — the postinst must run as
root). For quick testing over novacom, see the deferred-postinst note in CLAUDE.md.

## Critical gotchas (full list in CLAUDE.md)

- **Bump the app version to reload changed code** — webOS caches hard; a file swap alone won't load.
- **Use `XMLHttpRequest` + `JSON.parse`**, not `enyo.xhr`/`enyo.json` (they throw → white screen).
- **XHTML 1.1 doctype** + system `enyo/0.10/framework/enyo.js` for a themed app (like the 1p apps).
- **Testing the UI needs a human** to swipe-close + reopen the app (headless launch restores a cached card).
