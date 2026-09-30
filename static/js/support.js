/* ---------------------------------------------------------------------------
   ApplyBaMa - support.js
   The floating "Contact Support" button (templates/partials/support_button.html).

   Movement is deliberately constrained: dragging only ever
     * swaps the button between the LEFT and RIGHT screen edges, and
     * slides it vertically within the safe band (clear of the very top and
       bottom edges).
   The pointer's X decides the side, the pointer's Y decides the height — the
   button itself stays glued to the chosen edge, never floating into the page.
   The chosen spot and the minimized state are remembered in localStorage, so
   the button is where the visitor left it.

   Clicks vs. drags: a click opens the chat; a drag never triggers one. The
   link's default is suppressed during a real drag and the click handler
   navigates manually once the pointer is released without meaningful travel.
--------------------------------------------------------------------------- */

(function () {
    "use strict";

    var STORAGE_KEY = "abSupportWidget";
    // The button travels between these bands (fractions of the viewport
    // height, minus the button's own size), so it can never hide off-screen
    // or cover the very top / bottom of the page.
    var PROGRESS_MIN = 0;
    var PROGRESS_MAX = 1;
    // Clicks shorter than this are clicks; anything longer/farther is a drag.
    var DRAG_THRESHOLD_PX = 6;

    var state = { side: "end", progress: 0.62, minimized: false };

    function loadState() {
        try {
            var saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "null");
            if (saved && (saved.side === "start" || saved.side === "end")) {
                state.side = saved.side;
            }
            if (saved && typeof saved.progress === "number") {
                state.progress = Math.min(PROGRESS_MAX, Math.max(PROGRESS_MIN, saved.progress));
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

        var minButton = button.querySelector(".ab-support-min");
        var label = button.querySelector(".ab-support-label");
        var minLabel = button.getAttribute("data-support-min-label") || "";
        var minimizeTitle =
            (window.I18N && window.I18N.supportMinimize) || "Minimize";

        function applySide() {
            // inset-inline-* flip with the document direction, so the stored
            // logical side keeps its meaning in RTL too. The side is a class
            // (never an inline style): a fixed-position element that ends up
            // with both left and right insets set stretches full-width.
            button.classList.toggle("ab-support--start", state.side === "start");
            button.classList.toggle("ab-support--end", state.side !== "start");
            button.style.setProperty(
                "--ab-support-progress",
                String(state.progress)
            );
        }

        function applyMinimized() {
            button.classList.toggle("ab-support--minimized", state.minimized);
            // The bubble is small, so the accessible name moves to the button
            // itself and the minimize control is dropped from the tab order.
            if (minButton) {
                minButton.tabIndex = state.minimized ? -1 : 0;
            }
            button.title = state.minimized ? minLabel : "";
            button.setAttribute(
                "aria-label",
                state.minimized ? minLabel : minLabel
            );
            button.setAttribute(
                "aria-expanded",
                state.minimized ? "false" : "true"
            );
        }

        loadState();
        applySide();
        applyMinimized();

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
                saveState();
            });
        }

        /* ---------------- Drag along the side rail ---------------- */

        var drag = null;

        function pointerTravel(event) {
            // Where is the pointer within the vertical travel band?
            var height = window.innerHeight || 800;
            var topBand = 24; // px kept clear at the top
            var bottomBand = 40; // px kept clear at the bottom
            var travel = Math.max(1, height - topBand - bottomBand);
            return (event.clientY - topBand) / travel;
        }

        function pointerSide(event) {
            return event.clientX >= (window.innerWidth || 0) / 2 ? "end" : "start";
        }

        button.addEventListener("pointerdown", function (event) {
            if (event.button !== 0) return;
            // A drag started on the minimize control is a click on that
            // control; the control stops propagation anyway, this guards a
            // pointerdown that precedes its own click.
            if (event.target.closest(".ab-support-min")) return;
            drag = {
                startX: event.clientX,
                startY: event.clientY,
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
            state.progress = Math.min(
                PROGRESS_MAX,
                Math.max(PROGRESS_MIN, pointerTravel(event))
            );
            applySide();
        });

        function endDrag(event) {
            if (!drag) return;
            var wasDrag = drag.moved;
            drag = null;
            button.classList.remove("ab-support--dragging");
            if (wasDrag) {
                saveState();
                // Swallow the click that follows a drag so the chat does not
                // open as a side effect of moving the button.
                event.preventDefault();
                event.stopPropagation();
            }
        }

        button.addEventListener("pointerup", endDrag);
        button.addEventListener("pointercancel", endDrag);

        // Keyboard users move the button with the arrow keys instead of
        // dragging: left/right swaps the side, up/down adjusts the height.
        button.addEventListener("keydown", function (event) {
            var step = 0.08;
            if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
                state.side = event.key === "ArrowLeft" ? "start" : "end";
                applySide();
                saveState();
                event.preventDefault();
            } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                state.progress = Math.min(
                    PROGRESS_MAX,
                    Math.max(PROGRESS_MIN, state.progress + (event.key === "ArrowUp" ? -step : step))
                );
                applySide();
                saveState();
                event.preventDefault();
            }
        });

        // Double click on the bubble restores the full label.
        button.addEventListener("dblclick", function () {
            if (!state.minimized) return;
            state.minimized = false;
            applyMinimized();
            saveState();
            button.classList.add("ab-support--restoring");
            window.setTimeout(function () {
                button.classList.remove("ab-support--restoring");
            }, 300);
        });
    });
})();
