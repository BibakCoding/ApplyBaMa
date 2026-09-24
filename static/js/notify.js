/* ---------------------------------------------------------------------------
   ApplyBaMa - notify.js
   The single source of truth for user notifications across the whole site.

   Loaded from base.html, so there is exactly ONE configured Notyf instance and
   ONE entry point: window.notify(message, type). Page scripts must never
   construct their own Notyf — a local instance would ignore this configuration
   (position, colours, icons, durations) and could drift from it.

       window.notify("Saved successfully", "success");
       window.notify(data.errors, "error");   // array or "a\nb" both work

   Types: success | info (5s), warning (7s), error (8s). Errors linger longer
   because they usually need reading; successes should not block the view.
--------------------------------------------------------------------------- */
(function () {
    // notyf.min.js is loaded with `defer`, so it is not defined yet while the
    // document is still being parsed. The instance is therefore created lazily
    // (and idempotently) instead of at parse time.
    function notyfInstance() {
        if (!window.notyf && typeof Notyf !== 'undefined') {
            window.notyf = new Notyf(notyfOptions);
        }
        return window.notyf;
    }

    var notyfOptions = {
        duration: 5000,
        dismissible: true,
        position: {x: 'right', y: 'top'},
        types: [
            {
                type: 'success',
                duration: 5000,
                background: '#15803D',
                icon: {
                    className: 'fas fa-check-circle',
                    tagName: 'i',
                    color: 'white'
                }
            },
            {
                type: 'error',
                duration: 8000,
                background: '#B91C1C',
                icon: {
                    className: 'fas fa-exclamation-circle',
                    tagName: 'i',
                    color: 'white'
                }
            },
            {
                type: 'warning',
                duration: 7000,
                background: '#B45309',
                icon: {
                    className: 'fas fa-exclamation-triangle',
                    tagName: 'i',
                    color: 'white'
                }
            },
            {
                type: 'info',
                duration: 5000,
                background: '#0369A1',
                icon: {
                    className: 'fas fa-info-circle',
                    tagName: 'i',
                    color: 'white'
                }
            }
        ]
    };

    var ALIASES = {danger: 'error', warn: 'warning', debug: 'info', notice: 'info'};
    var KNOWN = ['success', 'error', 'warning', 'info'];

    /*
     * Canonical notification entry point.
     *
     * @param {string|string[]} message  text, or several lines/messages
     * @param {string}          type     success | error | warning | info
     * @returns {boolean}                true when at least one toast was shown
     *
     * Never throws: a notification failure must not abort the caller's flow
     * (e.g. a redirect or a form submission that already succeeded).
     */
    window.notify = function (message, type) {
        var items = (Array.isArray(message) ? message : String(message == null ? '' : message).split('\n'))
            .map(function (m) { return String(m).trim(); })
            .filter(Boolean);
        if (!items.length) return false;

        var kind = String(type || 'info').toLowerCase();
        kind = ALIASES[kind] || kind;
        if (KNOWN.indexOf(kind) === -1) kind = 'info';

        var inst = notyfInstance();
        if (!inst || typeof inst.open !== 'function') {
            // Notyf failed to load (blocked or missing vendor file): degrade to
            // the browser console rather than breaking the page.
            items.forEach(function (text) { console.log('[' + kind + '] ' + text); });
            return false;
        }

        items.forEach(function (text) {
            inst.open({type: kind, message: text});
        });
        return true;
    };

    // Server-side Django messages (login, logout, redirects, ...).
    //
    // These arrive as markup (#ab-server-messages in base.html) rather than as
    // interpolated JavaScript: the message text is HTML-escaped by Django, and
    // this file stays a plain, cacheable static asset with no template tags in
    // it. Reading them here also keeps working when a message contains
    // characters that would break an inline string literal.
    var levelMap = {
        'debug': 'info',
        'info': 'info',
        'success': 'success',
        'warning': 'warning',
        'error': 'error'
    };

    function showServerMessages() {
        // Pre-warm the instance so window.notyf is ready for any page script.
        notyfInstance();

        var nodes = document.querySelectorAll('#ab-server-messages [data-ab-message]');
        for (var i = 0; i < nodes.length; i++) {
            var level = levelMap[nodes[i].getAttribute('data-ab-level')] || 'info';
            window.notify(nodes[i].getAttribute('data-ab-message'), level);
        }
    }

    // The deferred Notyf script has definitely executed by DOMContentLoaded.
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', showServerMessages);
    } else {
        showServerMessages();
    }
})();
