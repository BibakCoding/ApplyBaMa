/* ==========================================================================
   ApplyBaMa - base.js
   Global JavaScript for the whole website.
========================================================================== */

(function () {
  "use strict";

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
        alert.style.transition = "opacity 300ms ease, transform 300ms ease";
        alert.style.opacity = "0";
        alert.style.transform = "translateY(-6px)";

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
