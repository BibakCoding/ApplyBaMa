/* ---------------------------------------------------------------------------
   ApplyBaMa - app-config.js
   Publishes the server's runtime configuration as window.AppConfig.

   The values are built by core.context_processors.app_config and emitted as a
   non-executable JSON data block (#ab-app-config) instead of an inline
   <script>. That means:

     * every URL is resolved once, in Python, so the home page and the dashboard
       cannot drift apart;
     * no page ships inline executable JavaScript, which cannot be cached and
       forces 'unsafe-inline' in any Content-Security-Policy.

   Loaded before any page script, so AppConfig is always defined.
   AppConfig.urls and AppConfig.translations are always objects; consumers can
   read a key without guarding against undefined.
--------------------------------------------------------------------------- */
(function () {
    "use strict";

    var config = {staticUrl: "", isLoggedIn: false, urls: {}, translations: {}};
    var el = document.getElementById("ab-app-config");

    if (el) {
        try {
            var parsed = JSON.parse(el.textContent);
            if (parsed && typeof parsed === "object") {
                config = parsed;
            }
        } catch (e) {
            // A malformed block must not take the page down: consumers fall
            // back to their own defaults (e.g. AppConfig.urls.x || "/fallback/").
            console.error("[app-config] could not parse #ab-app-config", e);
        }
    }

    config.urls = config.urls || {};
    config.translations = config.translations || {};

    window.AppConfig = config;
})();
