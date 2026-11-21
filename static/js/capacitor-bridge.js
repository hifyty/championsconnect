// Champions Connect -- native-app bridge (forward-compatible, no-op today).
//
// Today this app is served as a plain website/PWA, so `window.Capacitor`
// doesn't exist and every function below is a harmless no-op. Once the app
// is wrapped with Capacitor for the iOS/Android stores, any link or button
// marked `data-open-external` (the Give Online entry points) will open in
// the device's system browser instead of the app's embedded webview --
// which is what Apple's guidelines require for in-app giving/donations
// that aren't processed through Apple Pay / in-app purchase.
//
// Nothing here changes behavior on the regular website today.
(function () {
  function isNativeApp() {
    return !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
  }

  document.addEventListener('click', function (e) {
    if (!isNativeApp()) return; // normal web/PWA: do nothing, let the link work as-is

    var el = e.target.closest('[data-open-external]');
    if (!el) return;

    var url = el.getAttribute('href') || el.getAttribute('data-open-external');
    if (!url) return;

    if (window.Capacitor.Plugins && window.Capacitor.Plugins.Browser) {
      e.preventDefault();
      var fullUrl = url.indexOf('http') === 0 ? url : (window.location.origin + url);
      window.Capacitor.Plugins.Browser.open({ url: fullUrl });
    }
  });
})();
