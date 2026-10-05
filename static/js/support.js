/* ---------------------------------------------------------------------------
   ApplyBaMa - support.js
   The floating "Contact Support" button (templates/partials/support_button.html).

   Movement is deliberately constrained: dragging only ever
     * swaps the button between the LEFT and RIGHT screen edges, and
     * moves it vertically to wherever the pointer released it.
   The pointer's X decides the side (left half → left edge, right half → right
   edge), the pointer's Y decides the height — the button itself stays glued to
   the chosen edge, never floating into the middle of the page. Vertically the
   button follows the pointer one-to-one (minus the grab offset), clamped only
   so it can never end up off-screen. The chosen spot and the minimized state
   are remembered in localStorage, so the button is where the visitor left it.

   The anchor is `draggable="false"` (see the partial). A plain <a href> is
   natively draggable, and the browser's native drag would fire `dragstart` and
   cancel the pointer events this drag is built on — leaving the button stuck
   in place while the user drags. Disabling native drag lets the pointer flow
   below run; the click that follows a real drag is then swallowed explicitly
   (preventing the pointerup default does not cancel the click in browsers).

   Clicks vs. drags: a click opens the chat; a drag never triggers one.
--------------------------------------------------------------------------- */

(function () {
    "use strict";

    var STORAGE_KEY = "abSupportWidget";
    // The button is kept this far from the very top/bottom edges, so it can
    // never hide half off-screen after a drop at the extreme.
    var MARGIN_PX = 4;
    // Clicks shorter than this are clicks; anything longer/farther is a drag.
    var DRAG_THRESHOLD_PX = 6;
    // How long after a drag ends a follow-up click is treated as the drag's
    // tail rather than a real click.
    var CLICK_SUPPRESS_MS = 500;

    var state = { side: "end", top: null, minimized: false };
    var buttonElement = null;

    function viewportHeight() {
        return window.innerHeight || document.documentElement.clientHeight || 800;
    }

    function buttonHeight() {
        return buttonElement ? buttonElement.offsetHeight || 46 : 46;
    }

    // The highest/lowest top the button may take while staying fully on-screen.
    function clampTop(top) {
        var max = Math.max(MARGIN_PX, viewportHeight() - buttonHeight() - MARGIN_PX);
        return Math.min(max, Math.max(MARGIN_PX, top));
    }

    function loadState() {
        try {
            var saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
            if (saved && (saved.side === "start" || saved.side === "end")) {
                state.side = saved.side;
            }
            if (saved && typeof saved.top === "number") {
                state.top = saved.top;
            } else if (saved && typeof saved.progress === "number") {
                // Legacy format: a fraction of the travel band. Convert it to
                // the pixel position it used to map to so the button does not
                // jump for a visitor who moved it before this change.
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
        var minLabel = button.getAttribute("data-support-min-label") || "";
        var minimizeTitle =
            (window.I18N && window.I18N.supportMinimize) || "Minimize";

        // Set while the tail of a drag should not be read as a click.
        var suppressClickUntil = 0;

        function applyLayout() {
            // inset-inline-* flip with the document direction, so the stored
            // logical side keeps its meaning in RTL too. The side is a class
            // (never an inline style): a fixed-position element that ends up
            // with both left and right insets set stretches full-width.
            button.classList.toggle("ab-support--start", state.side === "start");
            button.classList.toggle("ab-support--end", state.side !== "start");
            if (typeof state.top === "number") {
                state.top = clampTop(state.top);
                button.style.setProperty("--ab-support-top", state.top + "px");
            }
        }

        function applyMinimized() {
            button.classList.toggle("ab-support--minimized", state.minimized);
            // The bubble is small, so the accessible name moves to the button
            // itself and the minimize control is dropped from the tab order.
            if (minButton) {
                minButton.tabIndex = state.minimized ? -1 : 0;
            }
            button.title = state.minimized ? minLabel : "";
            button.setAttribute("aria-label", minLabel);
            button.setAttribute(
                "aria-expanded",
                state.minimized ? "false" : "true"
            );
        }

        loadState();
        applyMinimized();
        applyLayout();

        // The small minus control minimizes; the bubble (the whole button,
        // minus the hidden control) restores on click.
        if (minButton) {
            minButton.title = minimizeTitle;
            minButton.setAttribute("aria-label", minimizeTitle);
            minButton.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                state.minimized = true;
                applyMinimized();
                // The bubble is shorter than the full pill: re-clamp so a drop
                // near the bottom edge does not leave it poking off-screen.
                applyLayout();
                saveState();
            });
        }

        /* ---------------- Drag along the side rail ---------------- */

        var drag = null;

        function pointerSide(event) {
            return event.clientX >= (window.innerWidth || 0) / 2 ? "end" : "start";
        }

        button.addEventListener("pointerdown", function (event) {
            if (event.button !== 0) return;
            // A drag started on the minimize control is a click on that
            // control; the control stops propagation anyway, this guards a
            // pointerdown that precedes its own click.
            if (event.target.closest(".ab-support-min")) return;
            var rect = button.getBoundingClientRect();
            drag = {
                startX: event.clientX,
                startY: event.clientY,
                // Where the pointer sits inside the button: the button follows
                // the pointer 1:1 from this grab point, so it lands exactly
                // where it was released.
                grabOffsetY: event.clientY - rect.top,
                moved: false,
                pointerId: event.pointerId,
            };
            button.setPointerCapture(event.pointerId);
        });

        button.addEventListener("pointermove", function (event) {
            if (!drag) return;
            if (Math.abs(event.clientX - drag.startX) > DRAG_THRESHOLD_PX ||
                Math.abs(event.clientY - drag.startY) > DRAG_THRESHOLD_PX) {
                drag.moved = true;
                button.classList.add("ab-support--dragging");
            }
            if (!drag.moved) return;
            event.preventDefault();
            state.side = pointerSide(event);
            state.top = clampTop(event.clientY - drag.grabOffsetY);
            applyLayout();
        });

        function endDrag(event) {
            if (!drag) return;
            var wasDrag = drag.moved;
            drag = null;
            button.classList.remove("ab-support--dragging");
            if (wasDrag) {
                saveState();
                // The click that follows the release is the drag's tail, not a
                // request to open the chat: swallow it (and any click the
                // browser fires shortly after) instead of navigating.
                suppressClickUntil = Date.now() + CLICK_SUPPRESS_MS;
                event.preventDefault();
                event.stopPropagation();
            }
        }

        button.addEventListener("pointerup", endDrag);
        button.addEventListener("pointercancel", endDrag);

        button.addEventListener("click", function (event) {
            if (Date.now() >= suppressClickUntil) return;
            suppressClickUntil = 0;
            event.preventDefault();
            event.stopPropagation();
        });

        // Keyboard users move the button with the arrow keys instead of
        // dragging: left/right swaps the side, up/down adjusts the height.
        button.addEventListener("keydown", function (event) {
            var current =
                typeof state.top === "number"
                    ? state.top
                    : button.getBoundingClientRect().top;
            if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
                state.side = event.key === "ArrowLeft" ? "start" : "end";
                applyLayout();
                saveState();
                event.preventDefault();
            } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                state.top = clampTop(current + (event.key === "ArrowUp" ? -16 : 16));
                applyLayout();
                saveState();
                event.preventDefault();
            }
        });

        // A viewport change can leave a stored position out of range.
        window.addEventListener("resize", function () {
            if (typeof state.top === "number") {
                applyLayout();
            }
        });

        // Double click on the bubble restores the full label.
        button.addEventListener("dblclick", function () {
            if (!state.minimized) return;
            state.minimized = false;
            applyMinimized();
            applyLayout();
            saveState();
            button.classList.add("ab-support--restoring");
            window.setTimeout(function () {
                button.classList.remove("ab-support--restoring");
            }, 300);
        });
    });
})();
