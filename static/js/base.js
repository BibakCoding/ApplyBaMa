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
    /* Sort labels, re-applied to the list pages' selects after each fragment
       injection. Options are re-keyed server-side on change, so the visible
       text has to keep matching the translated set rendered into base.html. */
    sortLabels: {
      "": document.body.dataset.i18nSortPlaceholder || "Sort By",
      name_asc: document.body.dataset.i18nSortNameAsc || "Sort: Name (A-Z)",
      name_desc: document.body.dataset.i18nSortNameDesc || "Sort: Name (Z-A)",
      university_asc:
        document.body.dataset.i18nSortUniversityAsc || "Sort: University (A-Z)",
      country_asc:
        document.body.dataset.i18nSortCountryAsc || "Sort: Country (A-Z)",
      fee_asc: document.body.dataset.i18nSortFeeAsc || "Sort: Fee (Low to High)",
      fee_desc:
        document.body.dataset.i18nSortFeeDesc || "Sort: Fee (High to Low)",
      founded_asc:
        document.body.dataset.i18nSortFoundedAsc || "Sort: Founded (Oldest First)",      founded_desc:
        document.body.dataset.i18nSortFoundedDesc ||
        "Sort: Founded (Newest First)",
    },
    /* Chat page strings (pages/chat.js), rendered into <body> by base.html. */
    chatNoConversations:
      document.body.dataset.i18nChatNoConversations || "No conversations yet.",
    chatNoConversationsSub:
      document.body.dataset.i18nChatNoConversationsSub ||
      "You can always message Support here; students an agent or company adds appear automatically.",
    chatNoMessages:
      document.body.dataset.i18nChatNoMessages || "No messages yet",
    chatSupportTag:
      document.body.dataset.i18nChatSupportTag || "Support",
    chatOnline: document.body.dataset.i18nChatOnline || "online",
    chatOffline: document.body.dataset.i18nChatOffline || "offline",
    chatTyping: document.body.dataset.i18nChatTyping || "typing…",
    chatDeletedMessage:
      document.body.dataset.i18nChatDeletedMessage || "Message deleted",
    chatEdited: document.body.dataset.i18nChatEdited || "(edited)",
    chatForwarded: document.body.dataset.i18nChatForwarded || "Forwarded",
    chatAttachment:
      document.body.dataset.i18nChatAttachment || "📎 Attachment",
    chatReply: document.body.dataset.i18nChatReply || "Reply",
    chatForward: document.body.dataset.i18nChatForward || "Forward",
    chatEdit: document.body.dataset.i18nChatEdit || "Edit",
    chatUnpin: document.body.dataset.i18nChatUnpin || "Unpin",
    chatPin: document.body.dataset.i18nChatPin || "Pin",
    chatDelete: document.body.dataset.i18nChatDelete || "Delete",
    chatDeleteConfirm:
      document.body.dataset.i18nChatDeleteConfirm ||
      "Delete this message for both sides?",
    chatRead: document.body.dataset.i18nChatRead || "Read",
    chatSent: document.body.dataset.i18nChatSent || "Sent",
    chatError: document.body.dataset.i18nChatError || "Something went wrong.",
    chatLoadError:
      document.body.dataset.i18nChatLoadError ||
      "Could not open the conversation.",
    chatFileNotAllowed:
      document.body.dataset.i18nChatFileNotAllowed ||
      "File sending is not enabled for your account. Ask the support team.",
    chatFileLimit:
      document.body.dataset.i18nChatFileLimit || "Files up to __MB MB",
    chatFileTooBig:
      document.body.dataset.i18nChatFileTooBig ||
      "This file is too large. Your limit is __MB MB.",
    chatForwardPrompt:
      document.body.dataset.i18nChatForwardPrompt ||
      "Forward this message to which conversation?\n\n",
    chatForwardedDone:
      document.body.dataset.i18nChatForwardedDone || "Message forwarded.",
    chatStartConversation:
      document.body.dataset.i18nChatStartConversation || "Start a conversation",
    chatGrantDone:
      document.body.dataset.i18nChatGrantDone || "File permission updated.",
    chatRevokeConfirm:
      document.body.dataset.i18nChatRevokeConfirm ||
      "Revoke this student's file permission?",
    chatRevoked:
      document.body.dataset.i18nChatRevoked || "File permission revoked.",
    supportMinimize:
      document.body.dataset.i18nSupportMinimize || "Minimize",
    /* Representation requests (pages/dashboard.js): the notification's "Go"
       deep link and the "Add by ID" dialog, rendered into <body> by
       base.html. */
    notificationGo: document.body.dataset.i18nNotificationGo || "Go",
    requestIdIncomplete:
      document.body.dataset.i18nRequestIdIncomplete ||
      "Enter the full 16-digit ID.",
    requestSending: document.body.dataset.i18nRequestSending || "Sending…",
    requestSent: document.body.dataset.i18nRequestSent || "Send request",
    requestDeclineConfirm:
      document.body.dataset.i18nRequestDeclineConfirm ||
      "Decline this representation request?",
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

    /* The token for an AJAX request, in order of reliability:

         1. a form's hidden input -- present whenever the caller is a form;
         2. the meta tag base.html renders on every page -- the only source
            that exists on a page with no form at all (an anonymous visitor on
            a marketing page, for example);
         3. the csrftoken cookie, which normally yields nothing because
            CSRF_COOKIE_HTTPONLY is on and JavaScript cannot read it. It stays
            last so this keeps working if that setting is ever relaxed.

       Returning "" rather than null keeps the type stable for callers. */
    getCsrfToken: function () {
      const csrfInput = document.querySelector(
        'input[name="csrfmiddlewaretoken"]',
      );
      return (
        (csrfInput && csrfInput.value) ||
        window.CSRF_TOKEN ||
        ApplyBaMa.getCookie("csrftoken") ||
        ""
      );
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
