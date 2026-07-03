/*
 * MainView — "Get Ready for OTA" (Part 1)
 *
 * Reads the fingerprint status the root daemon writes to
 *   /media/internal/.otaready/status.json  and tells the user whether they're
 *   ready, or what to do (advise-only). No package actions are taken here.
 *
 * UI follows the first-party Settings idiom (cf. com.palm.app.dateandtime):
 *   enyo-toolbar-light "header-welcome" bar with 48px icon + title,
 *   a Scroller with a 500px box-center column of captioned RowGroup/Item
 *   controls, and a bottom Toolbar. No emoji — 2011 WebKit has no color-emoji
 *   font; state is conveyed with colored headline text instead.
 *
 * On-device lessons baked in (learned from the System Updates reroute):
 *   - use plain XMLHttpRequest + JSON.parse; this Enyo build's enyo.xhr/enyo.json
 *     have an incompatible signature and throw during create() -> white screen.
 *   - stick to kinds the shipping 0.10 framework provides; everything below
 *     (VFlexBox, Scroller, RowGroup, Item, Spinner, Image, Toolbar, Button)
 *     is used by the stock Date & Time app.
 */
enyo.kind({
    name: "MainView",
    kind: "VFlexBox",
    className: "otaready enyo-bg",

    statusUrl: "file:///media/internal/.otaready/status.json",
    serverStateUrl: "file:///media/internal/.otaready/server-state.json",
    diagUrl: "file:///media/internal/.otaready/diagnostics.txt",
    curatorEmail: "curator@webosarchive.org",

    components: [
        { kind: "Control", className: "enyo-toolbar-light header-welcome", components: [
            { kind: "Image", src: "images/header-icon-otaready.png" },
            { content: "OTA Ready", style: "padding-left: 10px;" }
        ]},
        { kind: "Scroller", flex: 1, components: [
            { kind: "VFlexBox", className: "box-center", components: [
                { kind: "RowGroup", caption: "Status", components: [
                    { kind: "Item", tapHighlight: false, layoutKind: "HFlexLayout", align: "center", components: [
                        { name: "spinner", kind: "Spinner", showing: true },
                        { name: "statusText", flex: 1, className: "otaready-status", content: "Checking your device…" }
                    ]}
                ]},
                { name: "adviceGroup", kind: "RowGroup", caption: "What To Do", showing: false, components: [
                    { kind: "Item", tapHighlight: false, components: [
                        { name: "adviceText", className: "otaready-advice", allowHtml: true }
                    ]}
                ]},
                { name: "detailGroup", kind: "RowGroup", caption: "Device Details", showing: false, components: [
                    { kind: "Item", tapHighlight: false, layoutKind: "HFlexLayout", components: [
                        { flex: 1, content: "Model" },
                        { name: "valModel", className: "otaready-value" }
                    ]},
                    { kind: "Item", tapHighlight: false, layoutKind: "HFlexLayout", components: [
                        { flex: 1, content: "Baseline" },
                        { name: "valBaseline", className: "otaready-value" }
                    ]},
                    { kind: "Item", tapHighlight: false, layoutKind: "HFlexLayout", components: [
                        { flex: 1, content: "Kernel" },
                        { name: "valKernel", className: "otaready-value" }
                    ]},
                    { kind: "Item", tapHighlight: false, layoutKind: "HFlexLayout", components: [
                        { flex: 1, content: "Modern TLS" },
                        { name: "valTls", className: "otaready-value" }
                    ]},
                    { kind: "Item", tapHighlight: false, layoutKind: "HFlexLayout", components: [
                        { flex: 1, content: "Optware OpenSSL" },
                        { name: "valSsl", className: "otaready-value" }
                    ]},
                    { kind: "Item", tapHighlight: false, layoutKind: "HFlexLayout", components: [
                        { flex: 1, content: "Community Patches" },
                        { name: "valPatches", className: "otaready-value" }
                    ]}
                ]}
            ]}
        ]},
        { kind: "Toolbar", className: "enyo-toolbar-light", pack: "center", align: "center", components: [
            { kind: "Button", caption: "Check Again", onclick: "doCheck" },
            { name: "redirectBtn", kind: "Button", className: "enyo-button-affirmative",
              caption: "Use New Update Server", onclick: "doRedirect", showing: false }
        ]},
        // Bridge to the root daemon (writes .otaready/cmd). Enyo apps can't write
        // files, so the redirect handoff goes through this JS service.
        { name: "otareadyTrigger", kind: "PalmService",
          service: "palm://org.webosarchive.otaready.service/", method: "trigger",
          onSuccess: "onRedirectOk", onFailure: "onRedirectFail" },

        // Warn before redirecting: applying the patch restarts Luna, which looks
        // exactly like a crash if it happens with no heads-up.
        { name: "confirmDialog", kind: "Dialog", lazy: false, components: [
            { className: "otaready-dialog-title", content: "Switch to the new update server?" },
            { className: "otaready-dialog-text", allowHtml: true, content:
                "This sets up <b>System Updates</b> to read the community update server.<br><br>" +
                "Luna will restart, and all apps will be closed during the setup. " },
            { className: "otaready-dialog-buttons", layoutKind: "HFlexLayout", pack: "center", components: [
                { kind: "Button", caption: "Cancel", onclick: "cancelRedirect" },
                { kind: "Button", className: "enyo-button-affirmative", caption: "Continue", onclick: "confirmRedirect" }
            ]}
        ]},

        // Application menu (swipe down from the top-left corner).
        { kind: "AppMenu", components: [
            { caption: "Reset OTA Test", onclick: "doResetTest" },
            { caption: "Send Device Details", onclick: "doSendDetails" }
        ]},
        // Opens the email composer for "Send Device Details".
        { name: "appManager", kind: "PalmService",
          service: "palm://com.palm.applicationManager/", method: "open" }
    ],

    create: function() {
        this.inherited(arguments);
        this.doCheck();
    },

    doCheck: function() {
        this.$.spinner.show();
        this.$.statusText.removeClass("otaready-ready");
        this.$.statusText.removeClass("otaready-attention");
        this.$.statusText.setContent("Checking your device…");
        var self = this;
        // fingerprint first, then the server-relationship state, then render both
        this.fetchJson(this.statusUrl, function(s) {
            if (!s) { self.onError(); return; }
            self.lastStatus = s;
            self.fetchJson(self.serverStateUrl, function(ss) {
                self.lastServerState = ss || {};
                self.renderStatus(s, self.lastServerState);
            });
        });
    },

    fetchText: function(url, cb) {
        var req = new XMLHttpRequest();
        req.onreadystatechange = function() {
            if (req.readyState != 4) { return; }
            cb(req.responseText || "");
        };
        try {
            req.open("GET", url + "?t=" + (new Date()).getTime(), true);
            req.send(null);
        } catch (e) { cb(""); }
    },

    fetchJson: function(url, cb) {
        var req = new XMLHttpRequest();
        req.onreadystatechange = function() {
            if (req.readyState != 4) { return; }
            var v = null;
            try { v = JSON.parse(req.responseText); } catch (e) {}
            cb(v);
        };
        try {
            req.open("GET", url + "?t=" + (new Date()).getTime(), true);
            req.send(null);
        } catch (e) { cb(null); }
    },

    onError: function() {
        this.$.spinner.hide();
        this.$.statusText.setContent(
            "Couldn't read device status yet. The helper may still be starting — " +
            "wait a few seconds and tap Check Again.");
        this.$.adviceGroup.hide();
        this.$.detailGroup.hide();
        this.$.redirectBtn.hide();
    },

    renderStatus: function(s, ss) {
        this.$.spinner.hide();
        var view = this.viewFor(s, ss || {});
        this.$.statusText.setContent(view.headline);
        if (view.good) {
            this.$.statusText.addClass("otaready-ready");
            this.$.statusText.removeClass("otaready-attention");
        } else {
            this.$.statusText.addClass("otaready-attention");
            this.$.statusText.removeClass("otaready-ready");
        }
        this.$.adviceText.setContent(view.advice);
        this.$.adviceGroup.setShowing(!!view.advice);
        this.$.valModel.setContent(s.model || "—");
        this.$.valBaseline.setContent((s.verdict || "—") + " (L=" + s.L + " T=" + s.T + " Q=" + s.Q + ")");
        this.$.valKernel.setContent(s.kernel || "—");
        this.$.valTls.setContent(s.T === "1" ? "Yes" : "No");
        this.$.valSsl.setContent(s.optware_ssl || "none");
        this.$.valPatches.setContent((s.patches && s.patches.length) ? s.patches.join(", ") : "none");
        this.$.detailGroup.show();
        this.$.redirectBtn.setShowing(view.showRedirect);
    },

    // Compute headline / advice / button visibility. For a READY device this walks
    // the three server-relationship states from server-state.json; other devices
    // keep the advice-first flow (install TLS, remove kernel, …).
    viewFor: function(s, ss) {
        if (s.action !== "READY") {
            return { headline: this.headline(s), advice: this.advice(s),
                     good: false, showRedirect: false };
        }
        if (!ss.redirected) {
            // State 1 — ready, not yet re-pointed
            return {
                headline: "You're ready for the OTA",
                advice: "Your device has modern TLS and no blockers. Tap <b>Use New Update Server</b> " +
                        "below to point System Updates at the community update server.",
                good: true, showRedirect: true
            };
        }
        if (!ss.contacted) {
            // State 2 — re-pointed, no confirmed server check yet
            return {
                headline: "Pointed at the new update server",
                advice: "System Updates now checks the community server instead of Palm's. " +
                        "Waiting to confirm the connection — open <b>System Updates</b> and tap " +
                        "<b>Check Now</b>, or wait a moment and tap <b>Check Again</b>.",
                good: true, showRedirect: false
            };
        }
        // State 3 — re-pointed and a recorded successful server check
        var available = (ss.lastResult === "Available");
        return {
            headline: "Connected to the new update server",
            advice: "Last check " + this.esc(ss.lastContact) + " — " +
                    (available ? "an update is available." : "your device is up to date.") +
                    "<br>Open <b>System Updates</b> to " + (available ? "install it." : "check again."),
            good: true, showRedirect: false
        };
    },

    headline: function(s) {
        switch (s.action) {
            case "READY":         return "You're ready for the OTA";
            case "INSTALL_TLS":   return "Almost there — modern TLS is missing";
            case "REMOVE_KERNEL": return "A custom kernel is blocking the OTA";
            case "UNSUPPORTED":   return "This device isn't supported";
            case "REVIEW":        return "Your setup isn't recognized";
            default:              return "Status unavailable";
        }
    },

    advice: function(s) {
        switch (s.action) {
            case "READY":
                return "Your device has modern TLS and no blockers. Tap <b>Use New Update Server</b> " +
                       "below to point System Updates at the community update server.";
            case "INSTALL_TLS":
                return "Open <b>Preware</b>, make sure the <b>WOSA Modernize</b> feed is added, and install " +
                       "<b>“TLS 1.3 Updates”</b>. Then come back and tap <b>Check Again</b>.";
            case "REMOVE_KERNEL":
                return "You have a custom kernel installed:<br><i>" + this.esc(s.kernel) + "</i><br><br>" +
                       "Open <b>Preware</b> and remove it (e.g. UberKernel), reboot, then tap <b>Check Again</b>. " +
                       "The OTA rebuilds the boot image and would otherwise revert your kernel.";
            case "UNSUPPORTED":
                return "This update is only for the Wi-Fi HP TouchPad. Your device reports <i>" +
                       this.esc(s.model) + "</i> (" + this.esc(s.model_desc) + "), so it will not receive this OTA.";
            case "REVIEW":
                return "Your configuration doesn't match a known baseline, so we can't safely offer the OTA yet.<br>" +
                       this.esc(s.reason);
            default:
                return "";
        }
    },

    doRedirect: function() {
        this.$.confirmDialog.open();
    },

    cancelRedirect: function() {
        this.$.confirmDialog.close();
    },

    confirmRedirect: function() {
        this.$.confirmDialog.close();
        this.$.redirectBtn.setDisabled(true);
        this.$.adviceText.setContent(
            "Switching update server… the screen will reload in a moment. This is expected.");
        this.$.adviceGroup.show();
        this.$.otareadyTrigger.call({ cmd: "redirect" });
    },

    onRedirectOk: function(inSender, inResponse) {
        // The daemon restarts Luna right after applying the patch, so this often
        // won't run — the card is torn down first. Handle it anyway in case the
        // service reports a failure before any restart.
        if (inResponse && !inResponse.returnValue) {
            this.onRedirectFail(inSender, inResponse);
        }
    },

    onRedirectFail: function(inSender, inResponse) {
        this.$.adviceText.setContent(
            "Couldn't reach the OTA Ready helper service. If you just installed the app, reboot once " +
            "so the service registers, then try again.");
        this.$.redirectBtn.setDisabled(false);
    },

    // --- App menu: Reset OTA Test -------------------------------------------
    doResetTest: function() {
        this.$.otareadyTrigger.call({ cmd: "reset" });
        this.$.adviceText.setContent(
            "OTA Test reset. Open <b>System Updates</b> and tap <b>Check Now</b> — " +
            "the community update will be offered again.");
        this.$.adviceGroup.show();
        // re-read our own state once the daemon has re-offered
        var self = this;
        setTimeout(function() { self.doCheck(); }, 2500);
    },

    // --- App menu: Send Device Details --------------------------------------
    doSendDetails: function() {
        var self = this;
        // the daemon keeps a full diagnostic report fresh; fall back to what we have
        this.fetchText(this.diagUrl, function(body) {
            if (!body || body.length < 10) { body = self.fallbackDiagnostics(); }
            self.$.appManager.call({
                id: "com.palm.app.email",
                params: {
                    summary: "OTA Ready (Beta) device details",
                    text: body,
                    recipients: [{
                        type: "email", role: 1,
                        value: self.curatorEmail, contactDisplay: "webOS Archive Curator"
                    }]
                }
            });
        });
    },

    fallbackDiagnostics: function() {
        var s = this.lastStatus || {}, ss = this.lastServerState || {};
        var patches = (s.patches && s.patches.length) ? s.patches.join(", ") : "none";
        return "OTA Ready (Beta) device details\n\n" +
               "Model: " + (s.model || "?") + "\n" +
               "Baseline: " + (s.verdict || "?") + " (L=" + s.L + " T=" + s.T + " Q=" + s.Q + ")\n" +
               "Kernel: " + (s.kernel || "?") + "\n" +
               "Modern TLS: " + (s.T === "1" ? "yes" : "no") + "\n" +
               "Optware OpenSSL: " + (s.optware_ssl || "none") + "\n" +
               "Community patches: " + patches + "\n" +
               "Action: " + (s.action || "?") + "\n\n" +
               "Server: " + (ss.serverUrl || "?") + "\n" +
               "Re-pointed: " + (ss.redirected ? "yes" : "no") +
               ", contacted: " + (ss.contacted ? "yes" : "no") +
               ", last: " + (ss.lastContact || "never") + " (" + (ss.lastResult || "-") + ")\n";
    },

    esc: function(v) {
        if (v === undefined || v === null) { return ""; }
        return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
});
