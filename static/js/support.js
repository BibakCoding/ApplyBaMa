/* ---------------------------------------------------------------------------
   ApplyBaMa - support.js
   The floating "Contact Support" button (templates/partials/support_button.html).

   The button lives on the trailing edge of the viewport for its whole
   life: the edge itself is a logical CSS inset (`inset-inline-end`), so
   it is the right edge in LTR and the left edge in RTL with no
   per-locale code. Dragging is vertical only — the pointer's Y decides
   the height, the horizontal coordinate is never touched — and the
   resting height is kept on release, gliding into place through the
   `.ab-support--snapping` transition class rather than an inline
   transition. The height and the minimized state are remembered in
   localStorage, so the button is where the visitor left it.

   The anchor is `draggable="false"` (see the partial). A plain <a href>
   is natively draggable, and the browser's own drag would fire
   `dragstart` and cancel the pointer events this drag is built on —
   leaving the button stuck in place while the user drags. Disabling
   native drag lets the pointer flow below run; the click that follows a
   real drag is then swallowed explicitly (preventing the pointerup
   default does not cancel the click in browsers).

   While it rests, the button floats with a slow bob so it reads as
   "live"; the bob pauses during a drag and a snap so it can never fight
   those, and it is off entirely under prefers-reduced-motion.

   Clicks vs. drags: a click opens the admin chat; a drag never triggers
   one. Minimizing collapses it to a bubble that carries its own Expand
   control, so restoring is never a guess — and a double click is left
   free to mean "open the chat", which is what a double click on a link
   is expected to do.
--------------------------------------------------------------------------- */

(function () {
    "use strict";

    var STORAGE_KEY = "abSupportWidget";
    // The button is kept this far from the very top/bottom edges, so it
    // can never hide half off-screen after a drop at the extreme. The
    // margin also covers the resting bob (7px upward), so the float
    // never pokes above the top edge at the extreme position.
    var MARGIN_PX = 8;
    // A press that travels farther than this on either axis is a gesture, not
    // a click; the button itself only ever follows the vertical component.
    var DRAG_THRESHOLD_PX = 6;
    // How long after a drag ends a follow-up click is treated as the
    // drag's tail rather than a real click.
    var CLICK_SUPPRESS_MS = 500;
    // Upper bound for the release transition; the real duration lives in
    // the .ab-support--snapping rule in support.css.
    var SNAP_TIMEOUT_MS = 500;

    var state = { top: null, minimized: false };
    var buttonElement = null;

    // The layout viewport (clientWidth/Height), which excludes the
    // scrollbar — the same space clientY and a fixed element's insets
    // live in.
    function viewportHeight() {
        return document.documentElement.clientHeight || window.innerHeight || 800;
    }

    function buttonHeight() {
        return buttonElement ? buttonElement.offsetHeight || 46 : 46;
    }

    function clamp(value, min, max) {
        if (max < min) max = min;
        return Math.min(Math.max(min, value), max);
    }

    // The range the button's top may take while staying fully on-screen.
    function clampY(top) {
        return clamp(top, MARGIN_PX, viewportHeight() - buttonHeight() - MARGIN_PX);
    }

    function loadState() {
        try {
            var saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
            if (saved && typeof saved.top === "number") {
                state.top = saved.top;
            } else if (saved && typeof saved.progress === "number") {
                // Oldest format: a fraction of a travel band. Convert it to
                // the pixel position it used to map to so the button does
                // not jump for a visitor who moved it before that change.
                state.top = Math.round(24 + (viewportHeight() - 80) * saved.progress);
            }
            if (saved && typeof saved.minimized === "boolean") {
                state.minimized = saved.minimized;
            }
        } catch (e) {
            /* Private mode or corrupted data: the defaults stand. */
        }
    }

    function saveState() {
        try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (e) {
            /* Storage unavailable: the position just does not persist. */
        }
    }

    function ready(callback) {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", callback);
        } else {
            callback();
        }
    }

    ready(function () {
        var button = document.getElementById("abSupportBtn");
        if (!button) return;
        buttonElement = button;

        var minButton = button.querySelector(".ab-support-min");
        var expandButton = button.querySelector(".ab-support-expand");
        var minLabel = button.getAttribute("data-support-min-label") || "";
        var minimizeTitle =
            (window.I18N && window.I18N.supportMinimize) || "Minimize";
        var expandTitle = (window.I18N && window.I18N.supportExpand) || "Expand";

        // Set while the tail of a drag should not be read as a click.
        var suppressClickUntil = 0;
        // The release transition is class-driven; the timer is only its
        // failsafe (a dropped tab never fires transitionend).
        var snapTimer = null;

        function applyLayout() {
            // The trailing edge is the stylesheet's logical inset, so the
            // horizontal side is never a JavaScript concern — in RTL the
            // browser mirrors `inset-inline-end` onto the left edge for
            // free. Only the height is state.
            if (typeof state.top === "number") {
                state.top = clampY(state.top);
                button.style.top = state.top + "px";
            }
        }

        function applyMinimized() {
            button.classList.toggle("ab-support--minimized", state.minimized);
            // The bubble is small, so the accessible name moves to the
            // button itself and the controls hidden by the collapse leave
            // the tab order.
            if (minButton) minButton.tabIndex = state.minimized ? -1 : 0;
            if (expandButton) expandButton.tabIndex = state.minimized ? 0 : -1;
            button.title = state.minimized ? minLabel : "";
            button.setAttribute("aria-label", minLabel);
            button.setAttribute("aria-expanded", state.minimized ? "false" : "true");
        }

        function restore() {
            if (!state.minimized) return;
            state.minimized = false;
            applyMinimized();
            applyLayout();
            saveState();
            button.classList.add("ab-support--restoring");
            window.setTimeout(function () {
                button.classList.remove("ab-support--restoring");
            }, 300);
        }

        loadState();
        applyMinimized();
        applyLayout();

        // The minus control collapses the button to its bubble; the expand
        // control inside that bubble brings it back. Both are real buttons,
        // so neither relies on the whole-pill link or on a double click.
        if (minButton) {
            minButton.title = minimizeTitle;
            minButton.setAttribute("aria-label", minimizeTitle);
            minButton.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                state.minimized = true;
                applyMinimized();
                // The bubble is shorter than the full pill: re-clamp so a
                // saved height does not leave it poking off-screen.
                applyLayout();
                saveState();
            });
        }

        if (expandButton) {
            expandButton.title = expandTitle;
            expandButton.setAttribute("aria-label", expandTitle);
            expandButton.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                restore();
            });
        }

        /* ---------------- Vertical drag, snap on release ---------------- */

        var drag = null;

        button.addEventListener("pointerdown", function (event) {
            if (event.button !== 0) return;
            // A press on either control is a press on that control, never a
            // drag (and the control stops propagation anyway).
            if (event.target.closest(".ab-support-min, .ab-support-expand")) return;
            var rect = button.getBoundingClientRect();
            drag = {
                startX: event.clientX,
                startY: event.clientY,
                // Where the pointer sits inside the button: the button
                // follows the pointer 1:1 from this grab point, so it lands
                // where it was released, not shifted by where inside it the
                // user grabbed.
                offsetY: event.clientY - rect.top,
                moved: false,
                pointerId: event.pointerId,
            };
            button.setPointerCapture(event.pointerId);
        });

        button.addEventListener("pointermove", function (event) {
            if (!drag) return;
            // Movement on EITHER axis makes this a gesture. Only Y moves the
            // button — the trailing edge is fixed — but a press that slid
            // sideways and then released is still a gesture, not a click:
            // pointer capture keeps the click on the anchor no matter where
            // the pointer ended, so without the X test a sideways slide would
            // open the chat on release.
            if (
                Math.abs(event.clientY - drag.startY) > DRAG_THRESHOLD_PX ||
                Math.abs(event.clientX - drag.startX) > DRAG_THRESHOLD_PX
            ) {
                drag.moved = true;
                button.classList.add("ab-support--dragging");
            }
            if (!drag.moved) return;
            event.preventDefault();
            // The vertical axis only: the button is pinned to the trailing
            // edge by its CSS, so the pointer's X is ignored entirely and
            // the button can never cross to the other side. The height is
            // clamped so the button stays fully inside the viewport.
            button.style.top = clampY(event.clientY - drag.offsetY) + "px";
        });

        function endDrag(event) {
            if (!drag) return;
            var wasDrag = drag.moved;
            var dropY = event.clientY;
            var offsetY = drag.offsetY;
            drag = null;
            button.classList.remove("ab-support--dragging");
            if (!wasDrag) return;

            // The click that follows the release is the drag's tail, not a
            // request to open the chat: swallow it (and any click the
            // browser fires shortly after) instead of navigating.
            suppressClickUntil = Date.now() + CLICK_SUPPRESS_MS;
            event.preventDefault();
            event.stopPropagation();

            // Keep the height the button was released at (clamped), and
            // glide into it through the transition class — the animation
            // convention lives in the stylesheet, never in an inline
            // transition here.
            var top = clampY(dropY - offsetY);
            state.top = top;
            button.classList.add("ab-support--snapping");
            button.style.top = top + "px";
            saveState();
            window.clearTimeout(snapTimer);
            snapTimer = window.setTimeout(function () {
                button.classList.remove("ab-support--snapping");
            }, SNAP_TIMEOUT_MS);
        }

        button.addEventListener("pointerup", endDrag);
        button.addEventListener("pointercancel", endDrag);

        button.addEventListener("click", function (event) {
            // Every click inside the window is the drag's tail — a
            // double-click fires two of them, and the second must be
            // swallowed too, so the window is NOT disarmed here (it
            // expires on its own through the timestamp comparison).
            if (Date.now() >= suppressClickUntil) return;
            event.preventDefault();
            event.stopPropagation();
        });

        // Keyboard users move the button with the arrow keys: up and down
        // adjust the height. Left and right do nothing — the side is the
        // trailing edge and cannot be changed, by design.
        button.addEventListener("keydown", function (event) {
            if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                var current =
                    typeof state.top === "number" ? state.top : button.getBoundingClientRect().top;
                state.top = clampY(current + (event.key === "ArrowUp" ? -16 : 16));
                applyLayout();
                saveState();
                event.preventDefault();
            } else if (event.key === "Enter" || event.key === " ") {
                // Space/Enter is the link's own activation; the browser
                // handles it (a double click is never relied on to restore
                // the bubble).
                suppressClickUntil = 0;
            }
        });

        // A viewport change can leave a stored height out of range.
        window.addEventListener("resize", function () {
            if (typeof state.top === "number") {
                applyLayout();
            }
        });
    });
})();
