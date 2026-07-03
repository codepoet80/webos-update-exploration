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
          onSuccess: "onRedirectOk", onFailure: "onRedirectFail" }
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
        this.$.spinner.hide();
        this.$.statusText.setContent(
            "Couldn't read device status yet. The helper may still be starting — " +
            "wait a few seconds and tap Check Again.");
        this.$.adviceGroup.hide();
        this.$.detailGroup.hide();
        this.$.redirectBtn.hide();
    },

    renderStatus: function(s) {
        this.$.spinner.hide();
        var ready = (s.ready === true);
        this.$.statusText.setContent(this.headline(s));
        if (ready) {
            this.$.statusText.addClass("otaready-ready");
            this.$.statusText.removeClass("otaready-attention");
        } else {
            this.$.statusText.addClass("otaready-attention");
            this.$.statusText.removeClass("otaready-ready");
        }
        var advice = this.advice(s);
        this.$.adviceText.setContent(advice);
        this.$.adviceGroup.setShowing(!!advice);
        this.$.valModel.setContent(s.model || "—");
        this.$.valBaseline.setContent((s.verdict || "—") + " (L=" + s.L + " T=" + s.T + " Q=" + s.Q + ")");
        this.$.valKernel.setContent(s.kernel || "—");
        this.$.valTls.setContent(s.T === "1" ? "Yes" : "No");
        this.$.valSsl.setContent(s.optware_ssl || "none");
        this.$.valPatches.setContent((s.patches && s.patches.length) ? s.patches.join(", ") : "none");
        this.$.detailGroup.show();
        this.$.redirectBtn.setShowing(ready);
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
        this.$.redirectBtn.setDisabled(true);
        this.$.adviceText.setContent("Pointing System Updates at the community update server…");
        this.$.adviceGroup.show();
        this.$.otareadyTrigger.call({ cmd: "redirect" });
    },

    onRedirectOk: function(inSender, inResponse) {
        if (inResponse && inResponse.returnValue) {
            this.$.adviceText.setContent(
                "Done. Open <b>System Updates</b> and tap <b>Check Now</b> — it now reads the community " +
                "offer. (The screen may flash as it reloads.)");
        } else {
            this.onRedirectFail(inSender, inResponse);
            return;
        }
        this.$.redirectBtn.setDisabled(false);
    },

    onRedirectFail: function(inSender, inResponse) {
        this.$.adviceText.setContent(
            "Couldn't reach the OTA Ready helper service. If you just installed the app, reboot once " +
            "so the service registers, then try again.");
        this.$.redirectBtn.setDisabled(false);
    },

    esc: function(v) {
        if (v === undefined || v === null) { return ""; }
        return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
});
