/* ==========================================================================
   ApplyBaMa - base.js
   Global JavaScript for the whole website.
========================================================================== */

(function () {
  "use strict";

  /* --------------------------------------------------------------------------
     Server-rendered values, published as data rather than inline <script>
     blocks. Inline script cannot be cached, is re-sent with every response and
     forces 'unsafe-inline' in a Content-Security-Policy.
  -------------------------------------------------------------------------- */
  window.CSRF_TOKEN =
    (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  /* Carries a hero search across the register/login detour. Set by the home
     page's hero search as a query string ("page=programs&country=tr&degree=master");
     the dashboard view consumes it server-side, so it survives every redirect
     and any tab. The browser expires it after COOKIE_MAX_AGE seconds, which
     stops a half-finished search from hijacking a later login. */
  window.PendingSearch = {
    COOKIE: "pending_program_search",
    COOKIE_MAX_AGE: 300,
    set: function (query) {
      try {
        document.cookie =
          this.COOKIE +
          "=" +
          encodeURIComponent(query) +
          "; path=/; max-age=" +
          this.COOKIE_MAX_AGE +
          "; samesite=lax";
      } catch (e) {}
    },
  };

  /* Text that the page scripts display to the user.

     Files under static/js are served verbatim by the staticfiles app and are
     NEVER rendered as Django templates, so a translation tag written inside one
     would ship the raw tag text to the browser. The text is rendered into the
     <body> as data attributes instead (see base.html) and read here, so page
     scripts use window.I18N.<key> and can never leak an untranslated tag. */
  window.I18N = {
    unexpectedError:
      document.body.dataset.i18nUnexpectedError ||
      "An unexpected error occurred.",
  };

  const ApplyBaMa = {
    ready: function (callback) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", callback);
      } else {
        callback();
      }
    },

    qs: function (selector, context) {
      return (context || document).querySelector(selector);
    },

    qsa: function (selector, context) {
      return Array.from((context || document).querySelectorAll(selector));
    },

    getCookie: function (name) {
      let cookieValue = null;

      if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");

        for (let i = 0; i < cookies.length; i++) {
          const cookie = cookies[i].trim();

          if (cookie.substring(0, name.length + 1) === name + "=") {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
          }
        }
      }

      return cookieValue;
    },

    getCsrfToken: function () {
      const csrfInput = document.querySelector(
        'input[name="csrfmiddlewaretoken"]',
      );
      return csrfInput ? csrfInput.value : ApplyBaMa.getCookie("csrftoken");
    },
  };

  function initAlerts() {
    ApplyBaMa.qsa("[data-autohide]").forEach(function (alert) {
      const delay = parseInt(alert.getAttribute("data-autohide"), 10) || 4000;

      setTimeout(function () {
        // The fade state is a CSS class (see .ab-alert--hiding in base.css),
        // so presentation stays in the stylesheet instead of this script.
        alert.classList.add("ab-alert--hiding");

        setTimeout(function () {
          alert.remove();
        }, 300);
      }, delay);
    });

    ApplyBaMa.qsa(".ab-alert-close").forEach(function (button) {
      button.addEventListener("click", function () {
        const alert = button.closest(".ab-alert");
        if (alert) {
          alert.remove();
        }
      });
    });
  }

  function initCurrentYear() {
    ApplyBaMa.qsa("[data-current-year]").forEach(function (element) {
      element.textContent = new Date().getFullYear();
    });
  }

  function initSidebarToggle() {
    const toggle = ApplyBaMa.qs("[data-sidebar-toggle]");
    const sidebar = ApplyBaMa.qs("[data-sidebar]");

    if (!toggle || !sidebar) return;

    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("hidden");
    });
  }

  function initScrollProgress() {
    const bar = document.getElementById("ab-scroll-progress");
    if (!bar) return;

    const update = () => {
      const el = document.documentElement;
      const max = el.scrollHeight - el.clientHeight;
      bar.style.width = (max > 0 ? (el.scrollTop / max) * 100 : 0) + "%";
    };

    document.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  ApplyBaMa.ready(function () {
    initAlerts();
    initCurrentYear();
    initSidebarToggle();
    initScrollProgress();
  });

  window.ApplyBaMa = ApplyBaMa;
})();
