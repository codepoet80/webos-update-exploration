/*global fs */
/*
 * trigger {cmd: "check"|"redirect"|"revert"|"install"}
 *   -> writes the (whitelisted) word to /media/internal/.otaready/cmd
 *   -> the root otaready-daemon picks it up within ~1s and acts on it.
 *
 * `fs` is the node module required in index.js; source files share one scope
 * (same pattern as quickoffice's commands/DeleteFile.js using the global fs).
 */
var Trigger = function () {
};

Trigger.prototype = {
  run: function (future) {
    var ALLOWED = { check: 1, redirect: 1, revert: 1, install: 1 };
    var args = this.controller.args || {};
    var cmd = args.cmd;
    console.log("otaready Trigger.run cmd=" + cmd + " args=" + JSON.stringify(args));

    if (!cmd || !ALLOWED[cmd]) {
      console.log("otaready Trigger: rejected invalid cmd");
      future.result = { returnValue: false, errorText: "invalid cmd: " + cmd };
      return;
    }

    var dir = "/media/internal/.otaready";
    try {
      try { fs.mkdirSync(dir, 0755); } catch (e) { /* already exists */ }
      fs.writeFileSync(dir + "/cmd", cmd + "\n");
      console.log("otaready Trigger: wrote " + dir + "/cmd = " + cmd);
      future.result = { returnValue: true, queued: cmd };
    } catch (e) {
      console.log("otaready Trigger: write FAILED: " + String(e));
      future.result = { returnValue: false, errorText: "write failed: " + String(e) };
    }
  }
};
