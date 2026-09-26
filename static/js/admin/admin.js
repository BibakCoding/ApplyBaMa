/* ==========================================================================
   APPLY BM — DJANGO ADMIN BEHAVIOUR

   Vanilla JavaScript only (jQuery is not assumed even though the stock admin
   ships it). Loaded with `defer` from templates/admin/base_site.html.

   Two small, safe conveniences:

   1. "/" focuses Django's own sidebar filter (#nav-filter), the same key
      GitHub and most documentation sites use for their search box.
   2. A guard against navigating away from a half-filled change form. It only
      arms on *trusted* (real user) events, so widgets that fire synthetic
      change events during initialisation can never mark a pristine form dirty.
   ========================================================================== */
(function () {
    "use strict";

    var EDITABLE = ["input", "textarea", "select"];

    function isEditable(node) {
        if (!node || !node.tagName) {
            return false;
        }
        return EDITABLE.indexOf(node.tagName.toLowerCase()) !== -1 || node.isContentEditable === true;
    }

    /* ---------------------------------------------------------------------
       1. Keyboard shortcut: "/" focuses the sidebar filter
       --------------------------------------------------------------------- */
    document.addEventListener("keydown", function (event) {
        if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) {
            return;
        }
        if (isEditable(event.target)) {
            return;
        }
        var filter = document.getElementById("nav-filter");
        if (!filter) {
            return;
        }
        event.preventDefault();
        filter.focus();
        if (typeof filter.select === "function") {
            filter.select();
        }
    });

    /* ---------------------------------------------------------------------
       2. Unsaved-changes guard
       --------------------------------------------------------------------- */
    function initUnsavedGuard() {
        if (!document.body || document.body.classList.contains("change-form") === false) {
            return;
        }

        var form = document.querySelector("#content form[id$='_form']") ||
            document.querySelector("#content-main form");
        if (!form) {
            return;
        }

        var dirty = false;
        var submitted = false;

        function markDirty(event) {
            if (event.isTrusted === false) {
                return;
            }
            dirty = true;
            document.body.classList.add("admin-form-dirty");
        }

        form.addEventListener("input", markDirty);
        form.addEventListener("change", markDirty);
        form.addEventListener("submit", function () {
            submitted = true;
            document.body.classList.remove("admin-form-dirty");
        });

        window.addEventListener("beforeunload", function (event) {
            if (!dirty || submitted) {
                return undefined;
            }
            event.preventDefault();
            event.returnValue = "";
            return "";
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initUnsavedGuard);
    } else {
        initUnsavedGuard();
    }
})();
