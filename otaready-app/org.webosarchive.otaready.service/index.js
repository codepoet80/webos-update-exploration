/*global IMPORTS */
/*
 * OTA Ready command-bridge service.
 *
 * The Get Ready app and the patched System Updates app run in the WebKit app
 * jail and cannot write files (they can only XHR-read file://). This tiny node
 * service is the sanctioned bridge: it exposes one public `trigger` command that
 * writes a whitelisted command word into /media/internal/.otaready/cmd, which the
 * root otaready-daemon polls and acts on (check | redirect | revert | install).
 *
 * Structure mirrors the shipping com.quickoffice.webos.service (the reference
 * node/fs service on this webOS 3.0.5 build): IMPORTS.require, a service
 * assistant named in services.json, command assistants under commands/.
 */
var require = IMPORTS.require;

const fs = require('fs');

function OtareadyService() {
}

OtareadyService.prototype = {
  setup: function () {
    // nothing to warm up; the command does all the work synchronously
  }
};
