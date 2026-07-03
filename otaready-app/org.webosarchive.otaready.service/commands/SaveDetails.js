/*global fs */
/*
 * saveDetails — copy the daemon's diagnostics report to a user-visible file at
 * the root of /media/internal, so users without email set up can grab it off USB
 * storage. Returns the filename so the app can show it in a banner.
 *
 * The daemon writes .otaready/diagnostics.txt every poll; this just promotes the
 * latest copy to a plainly-named file the user can find when the TouchPad is
 * mounted as USB mass storage.
 */
var SaveDetails = function () {
};

SaveDetails.prototype = {
  run: function (future) {
    var src = "/media/internal/.otaready/diagnostics.txt";
    var name = "OTAReady-DeviceDetails.txt";
    var dst = "/media/internal/" + name;
    try {
      var data = fs.readFileSync(src);        // buffer copy — no encoding assumptions
      fs.writeFileSync(dst, data);
      console.log("otaready SaveDetails: wrote " + dst);
      future.result = { returnValue: true, filename: name, path: dst };
    } catch (e) {
      console.log("otaready SaveDetails: FAILED " + String(e));
      future.result = { returnValue: false, errorText: "save failed: " + String(e) };
    }
  }
};
