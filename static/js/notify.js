/* ---------------------------------------------------------------------------
   ApplyBaMa - notify.js
   The single source of truth for user notifications across the whole site.

   Loaded from base.html, so there is exactly ONE configured Notyf instance and
   ONE entry point: window.notify(). Page scripts must never construct their own
   Notyf — a local instance would ignore this configuration (position, colours,
   icons, durations) and could drift from it.

       window.notify("Saved successfully", "success");
       window.notify(data.errors, "error");   // array or "a\nb" both work
       window.notify({title: "New reply", message: "…", type: "info"});

   The plain form shows one toast per message. The structured form shows ONE
   toast with a title area (.ab-toast__title) and a description holding a
   summary of the message (.ab-toast__body) — a notification whose title and
   body are two separate banners reads as two unrelated events.

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

    // How much of a message body a structured toast shows. The full text is
    // always available in the notification itself; the toast is a heads-up.
    var SUMMARY_LENGTH = 120;

    function normaliseType(type) {
        var kind = String(type || 'info').toLowerCase();
        kind = ALIASES[kind] || kind;
        return KNOWN.indexOf(kind) === -1 ? 'info' : kind;
    }

    /*
     * Escape a value for the toast body.
     *
     * Notyf writes the message with innerHTML (notyf.min.js:
     * `r.innerHTML = t.message || ""`), so anything interpolated has to be
     * escaped here: notification titles and bodies come from the database and
     * must never be interpreted as markup.
     */
    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, function (ch) {
            return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch];
        });
    }

    // Collapse whitespace, then cut on a word boundary with an ellipsis, so the
    // description stays a summary whatever the message length is.
    function summarise(text, max) {
        var collapsed = String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
        if (collapsed.length <= max) return collapsed;
        var cut = collapsed.slice(0, max);
        var lastSpace = cut.lastIndexOf(' ');
        if (lastSpace > max * 0.6) cut = cut.slice(0, lastSpace);
        return cut.replace(/[\s.,;:!?…\-]+$/, '') + '…';
    }

    /*
     * One toast, two blocks: the title in the title area and a summary of the
     * body underneath it. Used by the structured form of window.notify.
     */
    function notifyStructured(title, body, type) {
        var kind = normaliseType(type);
        var heading = String(title == null ? '' : title).replace(/\s+/g, ' ').trim();
        var summary = summarise(body, SUMMARY_LENGTH);

        if (!heading && !summary) return false;

        var html = '';
        if (heading) html += '<span class="ab-toast__title">' + escapeHtml(heading) + '</span>';
        if (summary) html += '<span class="ab-toast__body">' + escapeHtml(summary) + '</span>';

        var inst = notyfInstance();
        if (!inst || typeof inst.open !== 'function') {
            // Notyf failed to load (blocked or missing vendor file): degrade to
            // the browser console rather than breaking the page.
            console.log('[' + kind + '] ' + heading + (summary ? ' - ' + summary : ''));
            return false;
        }

        inst.open({type: kind, message: html});
        return true;
    }

    /*
     * Canonical notification entry point.
     *
     * @param {string|string[]|object} message  text (one toast per line), or
     *        {title, message, type} for a title + description toast
     * @param {string}                  type     success | error | warning | info
     * @returns {boolean}                        true when a toast was shown
     *
     * Never throws: a notification failure must not abort the caller's flow
     * (e.g. a redirect or a form submission that already succeeded).
     */
    window.notify = function (message, type) {
        if (message && typeof message === 'object' && !Array.isArray(message)) {
            return notifyStructured(message.title, message.message, message.type || type);
        }

        var items = (Array.isArray(message) ? message : String(message == null ? '' : message).split('\n'))
            .map(function (m) { return String(m).trim(); })
            .filter(Boolean);
        if (!items.length) return false;

        var kind = normaliseType(type);
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
