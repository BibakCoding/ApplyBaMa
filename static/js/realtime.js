/* ---------------------------------------------------------------------------
   ApplyBaMa - realtime.js
   The single WebSocket client for the whole site.

   Connects to /ws/notify/ (authenticated users only — the server closes the
   socket for anonymous visitors) and dispatches every pushed event to
   document-level CustomEvents, so any page script can react without knowing
   about WebSockets:

       document.addEventListener("ab:notification-new", function (e) {
           console.log(e.detail.title, e.detail.unread_count);
       });

   Today the producers push "notification.new" (new platform notifications).
   The future chat feature will add its own event types on the same socket and
   the same dispatch mechanism — nothing here is notification-specific beyond
   the default listeners.

   Loaded from base.html after app-config.js/base.js, so window.AppConfig and
   window.ApplyBaMa exist. The script is a plain static asset: no template
   tags, no inline handlers, and every user-visible string comes from the
   window.I18N bridge rendered into base.html.
--------------------------------------------------------------------------- */
(function () {
    "use strict";

    var RECONNECT_BASE_MS = 1000;
    var RECONNECT_MAX_MS = 30000;

    var socket = null;
    var reconnectAttempt = 0;
    var reconnectTimer = null;
    var deliberatelyClosed = false;

    function wsUrl() {
        var cfg = window.AppConfig || {};
        if (!cfg.urls || !cfg.urls.notifySocket || !cfg.isLoggedIn) return null;
        // Build an absolute ws(s):// URL from the page's own origin, so the
        // socket always matches the scheme/host the page was served with
        // (wss behind HTTPS proxies, ws on plain-http development).
        var scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
        return scheme + "//" + window.location.host + cfg.urls.notifySocket;
    }

    function connect() {
        var url = wsUrl();
        if (!url) return; // anonymous visitor, or route not mounted
        if (socket && (socket.readyState === WebSocket.OPEN ||
                       socket.readyState === WebSocket.CONNECTING)) return;

        deliberatelyClosed = false;
        try {
            socket = new WebSocket(url);
        } catch (e) {
            scheduleReconnect();
            return;
        }

        socket.onopen = function () {
            reconnectAttempt = 0;
        };

        socket.onmessage = function (event) {
            var data;
            try {
                data = JSON.parse(event.data);
            } catch (e) {
                return; // never crash the page on a malformed frame
            }
            dispatch(data);
        };

        socket.onclose = function () {
            socket = null;
            if (!deliberatelyClosed) scheduleReconnect();
        };

        socket.onerror = function () {
            // onclose fires after onerror; reconnection is handled there.
        };
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        var delay = Math.min(
            RECONNECT_BASE_MS * Math.pow(2, reconnectAttempt),
            RECONNECT_MAX_MS
        );
        reconnectAttempt += 1;
        reconnectTimer = setTimeout(function () {
            reconnectTimer = null;
            connect();
        }, delay);
    }

    function dispatch(data) {
        if (!data || typeof data.type !== "string") return;

        // Handshake: let the page re-sync anything it may have missed.
        if (data.type === "connection.established") {
            document.dispatchEvent(new CustomEvent("ab:connected"));
            return;
        }
        if (data.type === "error.unsupported") return;

        // Every other event becomes ab:<type with dots as dashes>, e.g.
        // "notification.new" -> "ab:notification-new". The type stays in the
        // detail so listeners can tell event kinds apart. Producers add new
        // types without touching this file.
        var name = "ab:" + data.type.replace(/\./g, "-");
        document.dispatchEvent(new CustomEvent(name, { detail: data }));
    }

    /* ------------------------------------------------------------------
       Default listeners: the notification UX every authenticated page gets.
       Pages may also add their own listeners (the dashboard reloads the open
       "My Notifications" fragment on ab:notification-new).
    ------------------------------------------------------------------ */
    function setBadge(count) {
        var badge = document.getElementById("notifBadge");
        if (!badge) return;
        if (count > 0) {
            badge.textContent = count;
            badge.classList.remove("hidden");
            badge.classList.add("badge-pulse");
        } else {
            badge.classList.add("hidden");
            badge.classList.remove("badge-pulse");
        }
    }

    function onNotificationNew(event) {
        var d = event.detail || {};

        // 1. The sidebar unread badge, if this page has one.
        if (typeof d.unread_count === "number") setBadge(d.unread_count);

        // 2. A toast through the site's single notifier. Only genuinely new
        //    notifications toast here; read-state sync events just move the
        //    badge. The structured form of window.notify escapes the server
        //    text, so it cannot inject markup, and keeps the title and the
        //    message in ONE banner (title area + description).
        if (typeof window.notify === "function" && d.title) {
            window.notify({
                title: d.title,
                message: d.message,
                type: d.notification_type
            });
        }
    }

    function onNotificationsRead(event) {
        // Cross-tab read sync: another tab (or the same page's modal) marked
        // notifications read, so this tab's badge follows without polling.
        var d = event.detail || {};
        if (typeof d.unread_count === "number") setBadge(d.unread_count);
    }

    function onConnected() {
        // Fresh page load or a regained connection: re-sync the badge from
        // the server so nothing that arrived while the socket was down is
        // silently missing. dashboard.js keeps its own listener for list
        // fragments; the badge is handled here for every page.
        var cfg = window.AppConfig || {};
        if (!cfg.urls || !cfg.urls.unreadCount) return;
        fetch(cfg.urls.unreadCount, {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var badge = document.getElementById("notifBadge");
                if (!badge) return;
                if (data.count > 0) {
                    badge.textContent = data.count;
                    badge.classList.remove("hidden");
                    badge.classList.add("badge-pulse");
                } else {
                    badge.classList.add("hidden");
                    badge.classList.remove("badge-pulse");
                }
            })
            .catch(function () { /* badge stays as-is; polling is gone by design */ });
    }

    document.addEventListener("ab:notification-new", onNotificationNew);
    document.addEventListener("ab:notifications-read", onNotificationsRead);
    document.addEventListener("ab:connected", onConnected);

    // Reconnect when the tab becomes visible again: laptops sleep, sockets die.
    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible" &&
            (!socket || socket.readyState === WebSocket.CLOSED)) {
            reconnectAttempt = 0;
            connect();
        }
    });

    // Start after the deferred config scripts have run.
    (window.ApplyBaMa && window.ApplyBaMa.ready ? window.ApplyBaMa.ready : function (cb) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", cb);
        } else {
            cb();
        }
    })(connect);
})();
