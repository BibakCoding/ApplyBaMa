// static/js/pages/dashboard.js
document.addEventListener("DOMContentLoaded", function () {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("overlay");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const sidebarClose = document.getElementById("sidebarClose");
  const contentContainer = document.getElementById("dashboard-content");
  const navLinks = document.querySelectorAll(".nav-link");

  if (sidebarToggle)
    sidebarToggle.addEventListener("click", () => {
      sidebar.classList.add("open");
      overlay.classList.add("active");
    });
  if (sidebarClose) sidebarClose.addEventListener("click", closeSidebar);
  if (overlay) overlay.addEventListener("click", closeSidebar);

  function closeSidebar() {
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
  }

  // --- SPA Navigation (FIXED: handles 'page?params' as single arg) ---
  window.loadContent = function (page, params) {
    // 🔧 FIX: If page contains '?', split it
    if (page && page.includes("?")) {
      const parts = page.split("?");
      page = parts[0];
      params = parts[1] || "";
    }
    params = params || "";
    const queryString = params
      ? params.startsWith("?")
        ? params
        : "?" + params
      : "";
    const url =
      window.AppConfig.urls.dashboardContent.replace("PAGE_PLACEHOLDER", page) +
      queryString;

    contentContainer.innerHTML =
      '<div class="content-loading"><div class="spinner"></div><p>Loading...</p></div>';

    fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((r) => {
        if (!r.ok) throw new Error("Network error");
        return r.text();
      })
      .then((html) => {
        contentContainer.innerHTML = html;
        navLinks.forEach((link) => {
          link.classList.remove("active");
          if (link.getAttribute("data-page") === page)
            link.classList.add("active");
        });
        closeSidebar();
        const cleanParams = params.replace(/^\?/, "");
        const newUrl =
          window.location.pathname +
          "?page=" +
          page +
          (cleanParams ? "&" + cleanParams : "");
        window.history.pushState({ page: page }, "", newUrl);
        // Scroll to top of content
        contentContainer.scrollTop = 0;
      })
      .catch((err) => {
        contentContainer.innerHTML =
          '<div class="text-center py-12 text-red-500">Error loading content. Please refresh.</div>';
        console.error(err);
      });
  };

  navLinks.forEach((link) => {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      loadContent(this.getAttribute("data-page"));
    });
  });

  // --- Event Delegation: Forms ---
  contentContainer.addEventListener("submit", function (e) {
    const form = e.target.closest("form");
    if (!form) return;

    if (form.classList.contains("profile-form")) {
      e.preventDefault();
      handleProfileSubmit(form);
    } else if (form.id === "uniFilterForm" || form.id === "progFilterForm") {
      e.preventDefault();
      handleFilterSubmit(form);
    } else if (form.id === "newAppForm" || form.id === "addStudentForm") {
      e.preventDefault();
      handleJsonSubmit(form);
    } else if (
      form.classList.contains("delete-form") ||
      form.classList.contains("step-form")
    ) {
      e.preventDefault();
      handleJsonSubmit(form);
    } else if (form.id === "goToPageForm") {
      e.preventDefault();
      handleGoToPage(form);
    }
  });

  // --- Event Delegation: Clicks ---
  contentContainer.addEventListener("click", function (e) {
    // ========== GENERATE PASSWORD BUTTON ==========
    if (
      e.target.id === "generatePwdBtn" ||
      e.target.closest("#generatePwdBtn")
    ) {
      const genPwdUrl =
        window.AppConfig.urls.generatePassword ||
        "/dashboard/generate-password/";
      fetch(genPwdUrl)
        .then((r) => r.json())
        .then((data) => {
          const pwdInput = document.querySelector('input[name="password"]');
          if (pwdInput) pwdInput.value = data.password;
          showToast("Password generated successfully!", "success");
        })
        .catch(() => {
          showToast("Failed to generate password.", "error");
        });
    }

    // ========== COPY PASSWORD BUTTON ==========
    if (e.target.id === "copyPwdBtn" || e.target.closest("#copyPwdBtn")) {
      const pwdInput = document.querySelector('input[name="password"]');
      if (pwdInput && pwdInput.value) {
        navigator.clipboard
          .writeText(pwdInput.value)
          .then(() => {
            const btn =
              document.getElementById("copyPwdBtn") ||
              e.target.closest("#copyPwdBtn");
            const icon = btn.querySelector("i");
            if (icon) {
              icon.classList.replace("fa-copy", "fa-check");
              btn.classList.add("copied");
              showToast("Password copied to clipboard!", "success");
              setTimeout(() => {
                icon.classList.replace("fa-check", "fa-copy");
                btn.classList.remove("copied");
              }, 2000);
            }
          })
          .catch(() => {
            showToast("Failed to copy password.", "error");
          });
      } else {
        showToast("No password to copy. Generate one first.", "error");
      }
    }

    // ========== PASSWORD TOGGLE (Profile Page - .pwd-toggle-dash) ==========
    const pwdToggleDash = e.target.closest(".pwd-toggle-dash");
    if (pwdToggleDash) {
      const input = document.getElementById(pwdToggleDash.dataset.target);
      if (!input) return;
      const icon = pwdToggleDash.querySelector("i");
      if (input.type === "password") {
        input.type = "text";
        icon.classList.replace("fa-eye", "fa-eye-slash");
      } else {
        input.type = "password";
        icon.classList.replace("fa-eye-slash", "fa-eye");
      }
    }

    // ========== PASSWORD TOGGLE (Add Student Modal - .pwd-toggle) ==========
    const pwdToggle = e.target.closest(".pwd-toggle");
    if (pwdToggle) {
      const wrapper = pwdToggle.closest(".password-wrapper");
      if (!wrapper) return;
      const input = wrapper.querySelector(
        'input[type="password"], input[type="text"]',
      );
      if (!input) return;
      const icon = pwdToggle.querySelector("i");
      if (input.type === "password") {
        input.type = "text";
        if (icon) icon.classList.replace("fa-eye", "fa-eye-slash");
      } else {
        input.type = "password";
        if (icon) icon.classList.replace("fa-eye-slash", "fa-eye");
      }
    }

    // ========== APPLY REQUEST BUTTON (Programs Page) ==========
    const applyBtn = e.target.closest(".apply-request-btn");
    if (applyBtn) {
      const programId = applyBtn.dataset.programId;
      applyBtn.disabled = true;
      applyBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin mr-1"></i> Sending...';

      const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]");
      const formData = new FormData();
      formData.append("program_id", programId);
      if (csrfToken) formData.append("csrfmiddlewaretoken", csrfToken.value);

      fetch(
        window.AppConfig.urls.programApplyRequest ||
          "/dashboard/program-apply-request/",
        {
          method: "POST",
          body: formData,
          headers: { "X-Requested-With": "XMLHttpRequest" },
        },
      )
        .then((r) => r.json())
        .then((data) => {
          showToast(data.message, data.success ? "success" : "error");
          applyBtn.disabled = false;
          applyBtn.innerHTML = data.success
            ? '<i class="fas fa-check mr-1"></i> Sent!'
            : '<i class="fas fa-paper-plane mr-1"></i> Apply Request';
        })
        .catch(() => {
          showToast("Network error.", "error");
          applyBtn.disabled = false;
          applyBtn.innerHTML =
            '<i class="fas fa-paper-plane mr-1"></i> Apply Request';
        });
    }

    // ========== VIEW DETAILS BUTTON (Universities Page) ==========
    const viewDetailsBtn = e.target.closest(".view-details-btn");
    if (viewDetailsBtn) {
      const uniId = viewDetailsBtn.getAttribute("onclick").match(/id=(\d+)/);
      if (uniId && uniId[1]) {
        loadContent("university_detail?id=" + uniId[1]);
      }
    }
  });

  // --- Handlers ---
  function handleProfileSubmit(form) {
    const formData = new FormData(form);
    const btn = form.querySelector('button[type="submit"]');
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Saving...';
    fetch(form.action, {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken":
          window.CSRF_TOKEN ||
          document.querySelector("[name=csrfmiddlewaretoken]").value,
      },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          showToast(data.message, "success");
          setTimeout(() => loadContent("profile"), 1000);
        } else {
          showToast(data.errors ? data.errors.join("\n") : "Error", "error");
          btn.disabled = false;
          btn.innerHTML = orig;
        }
      })
      .catch(() => {
        showToast("Network error. Please try again.", "error");
        btn.disabled = false;
        btn.innerHTML = orig;
      });
  }

  function handleFilterSubmit(form) {
    const formData = new FormData(form);
    const params = new URLSearchParams(formData).toString();
    const page = form.id === "uniFilterForm" ? "universities" : "programs";
    loadContent(page, params);
  }

  function handleJsonSubmit(form) {
    if (form.classList.contains("delete-form") && !confirm("Are you sure?"))
      return;

    const formData = new FormData(form);
    const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]");

    // Ensure CSRF token is included
    if (csrfToken && !formData.has("csrfmiddlewaretoken")) {
      formData.append("csrfmiddlewaretoken", csrfToken.value);
    }

    const btn = form.querySelector('button[type="submit"]');
    const origText = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML =
        '<i class="fas fa-spinner fa-spin mr-2"></i> Processing...';
    }

    fetch(form.action, {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": window.CSRF_TOKEN || (csrfToken ? csrfToken.value : ""),
      },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          showToast(data.message || "Success", "success");
          const cur = window.history.state
            ? window.history.state.page
            : "my_applications";

          // Close modal if it exists
          const modal = document.getElementById("addStudentModal");
          if (modal) modal.classList.add("hidden");

          setTimeout(() => {
            loadContent(data.redirect ? "my_applications" : cur);
          }, 500);
        } else {
          const errDiv = form.querySelector("#formErrors");
          if (errDiv && data.errors) {
            errDiv.innerHTML = Object.entries(data.errors)
              .map(
                ([k, v]) =>
                  "<p>" +
                  k +
                  ": " +
                  (Array.isArray(v) ? v.join(", ") : v) +
                  "</p>",
              )
              .join("");
            errDiv.classList.remove("hidden");
          } else {
            showToast(data.message || "Error", "error");
          }
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = origText;
          }
        }
      })
      .catch((err) => {
        showToast("Network error. Please try again.", "error");
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = origText;
        }
      });
  }

  function handleGoToPage(form) {
    const pageInput = form.querySelector('input[name="goto_page"]');
    const targetPage = parseInt(pageInput.value);
    const section = form.dataset.section; // 'universities' or 'programs'
    const filters = form.dataset.filters || "";
    if (isNaN(targetPage) || targetPage < 1) {
      showToast("Please enter a valid page number.", "error");
      return;
    }
    const maxPage = parseInt(form.dataset.maxPage) || 999;
    if (targetPage > maxPage) {
      showToast("Page number cannot exceed " + maxPage + ".", "error");
      return;
    }
    loadContent(section, "page=" + targetPage + (filters ? "&" + filters : ""));
  }

  function showToast(message, type) {
    let c = document.getElementById("toast-container");
    if (!c) {
      c = document.createElement("div");
      c.id = "toast-container";
      c.className = "fixed top-4 right-4 z-50 space-y-3";
      document.body.appendChild(c);
    }
    const t = document.createElement("div");
    t.className =
      "p-4 rounded-lg shadow-lg text-white z-50 transition-all " +
      (type === "success" ? "bg-green-500" : "bg-red-500");
    t.innerText = message;
    c.appendChild(t);
    setTimeout(() => {
      t.style.opacity = "0";
      setTimeout(() => t.remove(), 300);
    }, 3500);
  }

  // --- Browser History (Back/Forward) ---
  window.addEventListener("popstate", function () {
    const p = new URLSearchParams(window.location.search);
    loadContent(p.get("page") || "welcome");
  });

  // --- Initial Load ---
  const p = new URLSearchParams(window.location.search);
  loadContent(p.get("page") || "welcome");
});
