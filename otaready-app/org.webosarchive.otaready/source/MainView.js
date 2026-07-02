/*
 * MainView — "Get Ready for OTA" (Part 1)
 *
 * Reads the fingerprint status the root daemon writes to
 *   /media/internal/.otaready/status.json  and tells the user whether they're
 *   ready, or what to do (advise-only). No package actions are taken here.
 *
 * On-device lessons baked in (learned from the System Updates reroute):
 *   - use plain XMLHttpRequest + JSON.parse; this Enyo build's enyo.xhr/enyo.json
 *     have an incompatible signature and throw during create() -> white screen.
 *   - stick to kinds proven present on this device: VFlexBox, FadeScroller,
 *     Toolbar, Button, and plain Controls (no "Header"/"PageHeader").
 */
enyo.kind({
    name: "MainView",
    kind: "VFlexBox",
    className: "otaready enyo-bg",

    statusUrl: "file:///media/internal/.otaready/status.json",

    components: [
        { className: "app-title", content: "Get Ready for OTA" },
        { kind: "FadeScroller", flex: 1, components: [
            { className: "body", components: [
                { name: "statusBox", className: "status-box", allowHtml: true, content: "Checking your device…" },
                { name: "adviceBox", className: "advice-box", allowHtml: true, showing: false },
                { name: "detailHdr", className: "detail-hdr", content: "Device details", showing: false },
                { name: "detailBox", className: "detail-box", allowHtml: true, showing: false }
            ]}
        ]},
        { kind: "Toolbar", className: "enyo-toolbar-light", components: [
            { kind: "Button", caption: "Check again", onclick: "doCheck" },
            { name: "redirectBtn", kind: "Button", caption: "Point me at the new server", onclick: "doRedirect", showing: false }
        ]}
    ],

    create: function() {
        this.inherited(arguments);
        this.doCheck();
    },

    doCheck: function() {
        this.$.statusBox.setContent("Checking your device…");
        var self = this;
        var req = new XMLHttpRequest();
        req.onreadystatechange = function() {
            if (req.readyState != 4) { return; }
            var s;
            try { s = JSON.parse(req.responseText); }
            catch (e) { self.onError(); return; }
            self.renderStatus(s);
        };
        try {
            req.open("GET", this.statusUrl + "?t=" + (new Date()).getTime(), true);
            req.send(null);
        } catch (e) { this.onError(); }
    },

    onError: function() {
        this.$.statusBox.setContent(
            "Couldn't read device status yet. The helper may still be starting — " +
            "wait a few seconds and tap “Check again”.");
        this.$.adviceBox.hide();
        this.$.detailHdr.hide();
        this.$.detailBox.hide();
        this.$.redirectBtn.hide();
    },

    renderStatus: function(s) {
        var ready = (s.ready === true);
        this.$.statusBox.setContent((ready ? "✅ " : "⚠️ ") + "<b>" + this.headline(s) + "</b>");
        this.$.adviceBox.setContent(this.advice(s));
        this.$.adviceBox.show();
        this.$.detailHdr.show();
        this.$.detailBox.setContent(this.details(s));
        this.$.detailBox.show();
        this.$.redirectBtn.setShowing(ready);
    },

    headline: function(s) {
        switch (s.action) {
            case "READY":         return "You're ready for the OTA.";
            case "INSTALL_TLS":   return "Almost there — modern TLS is missing.";
            case "REMOVE_KERNEL": return "A custom kernel is blocking the OTA.";
            case "UNSUPPORTED":   return "This device isn't supported.";
            case "REVIEW":        return "Your setup isn't recognized.";
            default:              return "Status unavailable.";
        }
    },

    advice: function(s) {
        switch (s.action) {
            case "READY":
                return "Your device has modern TLS and no blockers. Tap the button below to point it " +
                       "at the new update server.";
            case "INSTALL_TLS":
                return "Open <b>Preware</b>, make sure the <b>WOSA Modernize</b> feed is added, and install " +
                       "<b>“TLS 1.3 Updates”</b>. Then come back and tap <b>Check again</b>.";
            case "REMOVE_KERNEL":
                return "You have a custom kernel installed:<br><i>" + this.esc(s.kernel) + "</i><br><br>" +
                       "Open <b>Preware</b> and remove it (e.g. UberKernel), reboot, then tap <b>Check again</b>. " +
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

    details: function(s) {
        var patches = (s.patches && s.patches.length) ? s.patches.join(", ") : "none";
        return "Model: " + this.esc(s.model) + "<br>" +
               "Baseline: " + this.esc(s.verdict) + " (L=" + s.L + " T=" + s.T + " Q=" + s.Q + ")<br>" +
               "Kernel: " + this.esc(s.kernel) + "<br>" +
               "Modern TLS: " + (s.T === "1" ? "yes" : "no") + "<br>" +
               "Optware OpenSSL: " + this.esc(s.optware_ssl) + "<br>" +
               "Community patches: " + this.esc(patches);
    },

    doRedirect: function() {
        this.$.adviceBox.setContent(
            "Part 2 — repointing the device at the new update server — will hook into System Updates. " +
            "(Install handoff is being wired up.)");
    },

    esc: function(v) {
        if (v === undefined || v === null) { return ""; }
        return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
});
