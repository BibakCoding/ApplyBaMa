// static/js/pages/dashboard.js
document.addEventListener("DOMContentLoaded", function () {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("overlay");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const sidebarClose = document.getElementById("sidebarClose");
  const contentContainer = document.getElementById("dashboard-content");
  const navLinks = document.querySelectorAll(".nav-link");

  // Sidebar toggle logic for mobile view
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

  // Handles fetching and injecting SPA page fragments into the main dashboard container
  window.loadContent = function (page, params) {
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
        // Fragment requests must never inject the full dashboard layout
        // (e.g. login/permission redirects), which would nest a second sidebar
        if (r.redirected) throw new Error("Page not available");
        return r.text();
      })
      .then((html) => {
        contentContainer.innerHTML = html;

        // Highlight the active navigation link based on the loaded page
        navLinks.forEach((link) => {
          link.classList.remove("active");
          if (link.getAttribute("data-page") === page)
            link.classList.add("active");
        });

        closeSidebar();

        // Initialize page-specific logic after the new DOM elements are injected
        initProfileScripts();
        initSearchAutocomplete();
        initProgramAutocomplete();
        initSelect2();
        initNotificationsScripts();
        initMyNotificationsScripts();

        // Update the browser's address bar to reflect the current SPA state
        const cleanParams = params.replace(/^\?/, "");
        const newUrl =
          window.location.pathname +
          "?page=" +
          page +
          (cleanParams ? "&" + cleanParams : "");
        window.history.pushState({ page: page }, "", newUrl);

        contentContainer.scrollTop = 0;
      })
      .catch((err) => {
        contentContainer.innerHTML =
          '<div class="text-center py-12 text-red-500">Error loading content. Please refresh.</div>';
        console.error(err);
      });
  };

  // Attach SPA navigation listeners to sidebar links. Links without
  // data-page (e.g. the admin panel shortcut) keep default navigation.
  navLinks.forEach((link) => {
    link.addEventListener("click", function (e) {
      const page = this.getAttribute("data-page");
      if (!page) {
        closeSidebar();
        return;
      }
      e.preventDefault();
      loadContent(page);
    });
  });

  // Global event delegation for all forms inside the dynamic dashboard content
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
    } else if (form.id === "sendNotificationForm") {
      e.preventDefault();
      handleSendNotification(form);
    } else if (form.id === "goToPageForm") {
      e.preventDefault();
      handleGoToPage(form);
    }
  });

  // Global event delegation for dynamic click actions (password toggles, apply buttons, etc.)
  contentContainer.addEventListener("click", function (e) {
    if (
      e.target.id === "generatePwdBtn" ||
      e.target.closest("#generatePwdBtn")
    ) {
      fetch(
        window.AppConfig.urls.generatePassword ||
          "/dashboard/generate-password/",
      )
        .then((r) => r.json())
        .then((data) => {
          const pwdInput = document.querySelector('input[name="password"]');
          if (pwdInput) pwdInput.value = data.password;
          showToast("Password generated successfully!", "success");
        });
    }

    const pwdToggle = e.target.closest(".pwd-toggle-dash, .pwd-toggle");
    if (pwdToggle) {
      const targetId = pwdToggle.dataset.target;
      const wrapper = pwdToggle.closest(".password-wrapper");
      let input;

      if (targetId) input = document.getElementById(targetId);
      else if (wrapper)
        input = wrapper.querySelector(
          'input[type="password"], input[type="text"]',
        );

      if (input) {
        const icon = pwdToggle.querySelector("i");
        input.type = input.type === "password" ? "text" : "password";
        if (icon) {
          if (input.type === "password") {
            icon.classList.replace("fa-eye-slash", "fa-eye");
          } else {
            icon.classList.replace("fa-eye", "fa-eye-slash");
          }
        }
      }
    }

    const applyBtn = e.target.closest(".apply-request-btn");
    if (applyBtn) {
      const programId = applyBtn.dataset.programId;
      applyBtn.disabled = true;
      applyBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin mr-1"></i> Sending...';

      const formData = new FormData();
      formData.append("program_id", programId);
      const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]");
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
        });
    }
  });

  // Initializes specific UI components (like dropdowns and phone inputs) when a new fragment loads
  function initProfileScripts() {
    const mobileInput = document.getElementById("id_mobile");
    let iti = null;
    if (mobileInput && window.intlTelInput) {
      iti = window.intlTelInput(mobileInput, {
        utilsScript:
          "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/18.2.1/js/utils.js",
        separateDialCode: true,
        preferredCountries: ["tr", "ir", "de", "us"],
      });

      mobileInput.itiInstance = iti;

      // Normalizes international phone formats by stripping leading trunk zeros
      const removeLeadingZero = () => {
        if (mobileInput.value.startsWith("0")) {
          mobileInput.value = mobileInput.value.substring(1);
        }
      };

      const fixPlaceholder = () => {
        const countryData = iti.getSelectedCountryData();
        if (countryData.iso2 === "ir") {
          mobileInput.setAttribute("placeholder", "912 345 6789");
        } else if (countryData.iso2 === "tr") {
          mobileInput.setAttribute("placeholder", "501 234 56 78");
        }
      };

      iti.promise.then(() => {
        removeLeadingZero();
        fixPlaceholder();
      });

      mobileInput.addEventListener("countrychange", () => {
        setTimeout(removeLeadingZero, 10);
        fixPlaceholder();
      });

      mobileInput.addEventListener("input", () => {
        if (mobileInput.value.startsWith("0")) {
          const start = mobileInput.selectionStart;
          const end = mobileInput.selectionEnd;
          mobileInput.value = mobileInput.value.substring(1);
          mobileInput.setSelectionRange(
            Math.max(0, start - 1),
            Math.max(0, end - 1),
          );
        }
      });
    }

    // Cascading dropdown logic for Country -> City selection
    const countrySelect = document.getElementById("id_country");
    const citySelect = document.getElementById("id_city");
    if (countrySelect && citySelect) {
      countrySelect.addEventListener("change", function () {
        citySelect.innerHTML = '<option value="">---------</option>';
        if (!this.value) return;

        fetch(`/dashboard/get-cities/?country_id=${this.value}`)
          .then((res) => res.json())
          .then((data) => {
            if (data.cities) {
              data.cities.forEach((city) => {
                const opt = document.createElement("option");
                opt.value = city.id;
                opt.textContent = city.name;
                citySelect.appendChild(opt);
              });
            }
          });
      });
    }
  }

  // Fetches search results dynamically and provides a rich dropdown experience
  function initSearchAutocomplete() {
    let searchTimeout;
    const searchInputs = document.querySelectorAll(".search-input");

    searchInputs.forEach((input) => {
      const resultsDiv = input.nextElementSibling;
      if (!resultsDiv || !resultsDiv.classList.contains("search-results"))
        return;

      const isProgramSearch =
        input.placeholder &&
        input.placeholder.toLowerCase().includes("program");
      const url = isProgramSearch
        ? window.AppConfig.urls.programsSearch || "/dashboard/programs-search/"
        : window.AppConfig.urls.universitiesSearch ||
          "/dashboard/universities-search/";

      const fetchResults = (q) => {
        fetch(`${url}?q=${encodeURIComponent(q || "")}`)
          .then((r) => r.json())
          .then((data) => {
            resultsDiv.innerHTML = "";
            resultsDiv.classList.remove("hidden");
            if (data.results.length === 0) {
              resultsDiv.innerHTML =
                '<div class="p-2 text-sm text-gray-500">No results found</div>';
              return;
            }
            data.results.forEach((p) => {
              const div = document.createElement("div");
              div.className =
                "p-2 hover:bg-blue-50 cursor-pointer border-b text-sm text-gray-700";
              div.textContent = p.text;
              div.onclick = () => {
                input.value = p.text;
                resultsDiv.classList.add("hidden");
                const form = input.closest("form");
                if (form) {
                  form.dispatchEvent(new Event("submit", { cancelable: true }));
                }
              };
              resultsDiv.appendChild(div);
            });
          });
      };

      input.addEventListener("focus", function () {
        fetchResults(this.value);
      });

      input.addEventListener("input", function () {
        clearTimeout(searchTimeout);
        const q = this.value;
        searchTimeout = setTimeout(() => {
          fetchResults(q);
        }, 300);
      });

      document.addEventListener("click", function (e) {
        if (
          resultsDiv &&
          !resultsDiv.contains(e.target) &&
          e.target !== input
        ) {
          resultsDiv.classList.add("hidden");
        }
      });
    });
  }

  // Fetches matching university programs asynchronously as the user types
  function initProgramAutocomplete() {
    const searchInput = document.getElementById("program-search-input");
    const hiddenSelect = document.getElementById("id_program");
    const resultsDiv = document.getElementById("program-results");
    if (!searchInput || !hiddenSelect || !resultsDiv) return;

    let timeout;

    const fetchPrograms = (q) => {
      fetch(`/dashboard/programs-search/?q=${encodeURIComponent(q || "")}`)
        .then((r) => r.json())
        .then((data) => {
          resultsDiv.innerHTML = "";
          resultsDiv.classList.remove("hidden");
          if (data.results.length === 0) {
            resultsDiv.innerHTML =
              '<div class="p-2 text-sm text-gray-500">No results found</div>';
            return;
          }
          data.results.forEach((p) => {
            const div = document.createElement("div");
            div.className =
              "p-2 hover:bg-blue-50 cursor-pointer border-b text-sm";
            div.textContent = p.text;
            div.onclick = () => {
              hiddenSelect.innerHTML = `<option value="${p.id}" selected>${p.text}</option>`;
              searchInput.value = p.text;
              resultsDiv.classList.add("hidden");
            };
            resultsDiv.appendChild(div);
          });
        });
    };

    searchInput.addEventListener("focus", function () {
      fetchPrograms(this.value);
    });

    searchInput.addEventListener("input", function () {
      clearTimeout(timeout);
      const q = this.value;
      timeout = setTimeout(() => {
        fetchPrograms(q);
      }, 300);
    });

    document.addEventListener("click", function (e) {
      if (
        resultsDiv &&
        !resultsDiv.contains(e.target) &&
        e.target !== searchInput
      ) {
        resultsDiv.classList.add("hidden");
      }
    });
  }

  // Upgrades standard select tags to searchable dropdowns if Select2 is loaded
  function initSelect2() {
    if (window.jQuery && typeof window.jQuery.fn.select2 !== "undefined") {
      window.jQuery(".filter-select").each(function () {
        if (!window.jQuery(this).hasClass("select2-hidden-accessible")) {
          window.jQuery(this).select2({
            allowClear: true,
            width: "100%",
            placeholder: " ",
          });
        }
      });
    }
  }

  function initNotificationsScripts() {
    const recipientSelect = document.getElementById("recipientTypeSelect");
    const specificSection = document.getElementById("specificUsersSection");
    const searchInput = document.getElementById("userSearchInput");
    const searchResults = document.getElementById("searchResults");
    const selectedList = document.getElementById("selectedUsersList");
    const userIdsInput = document.getElementById("userIdsInput");

    if (!recipientSelect) return;

    let selectedUsers = new Set();

    const updateSelectedUI = () => {
      userIdsInput.value = Array.from(selectedUsers).join(",");
      selectedList.innerHTML = "";
      selectedUsers.forEach((id) => {
        const chip = document.createElement("span");
        chip.className = "px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm flex items-center space-x-2";
        const span = document.createElement("span");
        span.textContent = `ID: ${id}`;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "text-blue-600 hover:text-red-600";
        btn.innerHTML = '<i class="fas fa-times"></i>';
        btn.onclick = () => {
          selectedUsers.delete(id.toString());
          updateSelectedUI();
          const cb = searchResults ? searchResults.querySelector(`input.user-checkbox[value="${id}"]`) : null;
          if (cb) cb.checked = false;
        };
        chip.appendChild(span);
        chip.appendChild(btn);
        selectedList.appendChild(chip);
      });
    };

    const renderSearchResults = (data) => {
      searchResults.innerHTML = "";
      const groups = { default: "Students", company: "Company", agent: "Agents" };
      let hasResults = false;

      for (const [groupKey, label] of Object.entries(groups)) {
        if (data[groupKey] && data[groupKey].length > 0) {
          hasResults = true;
          const groupDiv = document.createElement("div");
          groupDiv.className = "mb-2";

          const header = document.createElement("div");
          header.className = "font-semibold text-sm text-gray-700 border-b mb-1 pb-1";
          header.textContent = label;
          groupDiv.appendChild(header);

          data[groupKey].forEach((user) => {
            const div = document.createElement("div");
            div.className = "flex items-center p-2 hover:bg-gray-50 rounded";

            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.className = "user-checkbox mr-2";
            cb.value = user.id;
            cb.dataset.username = user.username;
            cb.dataset.fullname = user.full_name;
            if (selectedUsers.has(user.id.toString())) cb.checked = true;

            cb.onchange = () => {
              if (cb.checked) {
                selectedUsers.add(user.id.toString());
              } else {
                selectedUsers.delete(user.id.toString());
              }
              updateSelectedUI();
            };

            const labelEl = document.createElement("label");
            labelEl.className = "text-sm text-gray-800 cursor-pointer";
            labelEl.textContent = `${user.username} ${user.full_name ? `(${user.full_name})` : ""}`;

            div.appendChild(cb);
            div.appendChild(labelEl);
            groupDiv.appendChild(div);
          });
          searchResults.appendChild(groupDiv);
        }
      }

      if (!hasResults) {
        searchResults.innerHTML = '<p class="text-sm text-gray-500 p-2">No users found.</p>';
      }
      searchResults.classList.remove("hidden");
    };

    recipientSelect.addEventListener("change", function () {
      if (this.value === "specific") {
        specificSection.classList.remove("hidden");
      } else {
        specificSection.classList.add("hidden");
      }
    });

    if (searchInput) {
      let timeout;
      searchInput.addEventListener("input", function () {
        clearTimeout(timeout);
        const q = this.value;
        timeout = setTimeout(() => {
          fetch(`${window.AppConfig.urls.searchUsers}?q=${encodeURIComponent(q)}`, {
            headers: { "X-Requested-With": "XMLHttpRequest" }
          })
            .then((r) => r.json())
            .then((data) => renderSearchResults(data));
        }, 300);
      });
      searchInput.addEventListener("focus", function () {
        if (this.value) {
          fetch(`${window.AppConfig.urls.searchUsers}?q=${encodeURIComponent(this.value)}`, {
            headers: { "X-Requested-With": "XMLHttpRequest" }
          })
            .then((r) => r.json())
            .then((data) => renderSearchResults(data));
        } else {
          searchResults.classList.remove("hidden");
          if (searchResults.innerHTML === "") {
             searchResults.innerHTML = '<p class="text-sm text-gray-500 p-2">Start typing to search...</p>';
          }
        }
      });
    }

    document.addEventListener("click", function (e) {
      if (searchResults && !searchResults.contains(e.target) && e.target !== searchInput) {
        searchResults.classList.add("hidden");
      }
    });

    document.querySelectorAll(".group-checkbox").forEach((cb) => {
      cb.addEventListener("change", function () {
        const group = this.dataset.group;
        fetch(`${window.AppConfig.urls.getGroupUsers}?group=${group}`, {
          headers: { "X-Requested-With": "XMLHttpRequest" }
        })
          .then((r) => r.json())
          .then((data) => {
            if (data.ids) {
              if (cb.checked) {
                data.ids.forEach((id) => selectedUsers.add(id.toString()));
              } else {
                data.ids.forEach((id) => selectedUsers.delete(id.toString()));
              }
              updateSelectedUI();
              if (searchResults) {
                searchResults.querySelectorAll(".user-checkbox").forEach((ucb) => {
                  if (data.ids.includes(parseInt(ucb.value))) {
                    ucb.checked = cb.checked;
                  }
                });
              }
            }
          });
      });
    });

    updateSelectedUI();
  }

  function initMyNotificationsScripts() {
    const modal = document.getElementById("notificationModal");
    const modalContent = document.getElementById("modalContent");
    const closeModalBtn = document.getElementById("closeModalBtn");
    const markAllBtn = document.getElementById("markAllReadBtn");

    if (!modal) return;

    document.querySelectorAll(".notification-item").forEach((item) => {
      item.addEventListener("click", function () {
        const id = this.dataset.id;
        fetch(`/dashboard/notifications/detail/${id}/`, {
          headers: { "X-Requested-With": "XMLHttpRequest" }
        })
          .then((r) => r.json())
          .then((data) => {
            if (data.success) {
              let typeBadge = "";
              if (data.type === "success") typeBadge = '<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">Success</span>';
              else if (data.type === "warning") typeBadge = '<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">Warning</span>';
              else if (data.type === "error") typeBadge = '<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">Error</span>';
              else if (data.type === "info") typeBadge = '<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">Info</span>';
              else typeBadge = '<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">Reminder</span>';

              modalContent.innerHTML = `
                <div class="mb-4">${typeBadge}</div>
                <h3 class="text-xl font-bold text-gray-900 mb-2">${data.title}</h3>
                <p class="text-gray-600 mb-4 whitespace-pre-wrap">${data.message}</p>
                <p class="text-sm text-gray-500">${data.date}</p>
              `;
              modal.classList.remove("hidden");

              const dot = item.querySelector(".w-3.h-3.bg-blue-600");
              if (dot) dot.remove();
              item.classList.remove("bg-blue-50", "border-blue-200");
              item.classList.add("bg-gray-50", "border-gray-200");

              updateUnreadBadge();
            }
          });
      });
    });

    if (closeModalBtn) {
      closeModalBtn.addEventListener("click", () => modal.classList.add("hidden"));
      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.classList.add("hidden");
      });
    }

    if (markAllBtn) {
      markAllBtn.addEventListener("click", function () {
        const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;
        fetch(window.AppConfig.urls.markAllRead, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrfToken
          }
        })
          .then((r) => r.json())
          .then((data) => {
            if (data.success) {
              showToast("All notifications marked as read.", "success");
              setTimeout(() => loadContent("my_notifications"), 500);
            }
          });
      });
    }
  }

  function updateUnreadBadge() {
    if (!window.AppConfig.urls.unreadCount) return;
    fetch(window.AppConfig.urls.unreadCount, {
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
      .then((r) => r.json())
      .then((data) => {
        const badge = document.getElementById("notifBadge");
        if (badge) {
          if (data.count > 0) {
            badge.textContent = data.count;
            badge.classList.remove("hidden");
          } else {
            badge.classList.add("hidden");
          }
        }
      });
  }

  function handleSendNotification(form) {
    const formData = new FormData(form);
    const recipientType = formData.get("recipient_type");
    if (recipientType === "specific") {
      const userIds = document.getElementById("userIdsInput").value;
      if (!userIds) {
        showToast("Please select at least one user.", "error");
        return;
      }
      formData.append("user_ids", userIds);
    }

    const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Sending...';

    fetch(window.AppConfig.urls.sendNotification, {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken
      }
    })
      .then((r) => r.json())
      .then((data) => {
        btn.disabled = false;
        btn.innerHTML = "Send Notification";
        if (data.success) {
          showToast(data.message, "success");
          setTimeout(() => loadContent("notifications"), 500);
        } else {
          showToast(data.message || "Error sending notification.", "error");
        }
      });
  }

  // Processes standard profile settings forms via AJAX to prevent full page reloads
  function handleProfileSubmit(form) {
    const mobileInput = form.querySelector("#id_mobile");
    if (mobileInput && mobileInput.itiInstance) {
      mobileInput.value = mobileInput.itiInstance.getNumber();
    }

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
      });
  }

  // Serializes filter forms and updates the SPA URL parameters
  function handleFilterSubmit(form) {
    const formData = new FormData(form);
    const params = new URLSearchParams(formData).toString();
    const page = form.id === "uniFilterForm" ? "universities" : "programs";
    loadContent(page, params);
  }

  // General purpose handler for complex dashboard forms (creation, deletion, step updates)
  function handleJsonSubmit(form) {
    if (form.classList.contains("delete-form") && !confirm("Are you sure?"))
      return;

    const formData = new FormData(form);
    const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]");
    if (csrfToken && !formData.has("csrfmiddlewaretoken")) {
      formData.append("csrfmiddlewaretoken", csrfToken.value);
    }

    const btn = form.querySelector('button[type="submit"]');
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
          const modal = document.getElementById("addStudentModal");
          if (modal) modal.classList.add("hidden");

          setTimeout(() => {
            const cur = window.history.state
              ? window.history.state.page
              : "my_applications";
            loadContent(data.redirect ? "my_applications" : cur);
          }, 500);
        } else {
          const errDiv = form.querySelector("#formErrors");
          if (errDiv && data.errors) {
            errDiv.innerHTML = Object.entries(data.errors)
              .map(
                ([k, v]) =>
                  `<p>${k}: ${Array.isArray(v) ? v.join(", ") : v}</p>`,
              )
              .join("");
            errDiv.classList.remove("hidden");
          } else {
            showToast(data.message || "Error", "error");
          }
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = "Submit";
          }
        }
      });
  }

  // Manages manual pagination inputs for large data tables
  function handleGoToPage(form) {
    const pageInput = form.querySelector('input[name="goto_page"]');
    const targetPage = parseInt(pageInput.value);
    const section = form.dataset.section;
    const filters = form.dataset.filters || "";

    if (isNaN(targetPage) || targetPage < 1) {
      showToast("Please enter a valid page number.", "error");
      return;
    }
    loadContent(section, "page=" + targetPage + (filters ? "&" + filters : ""));
  }

  // Generates and injects non-blocking toast messages securely at the document root
  function showToast(message, type) {
    let c = document.querySelector("body > #toast-container");
    if (!c) {
      // Clean up any legacy containers trapped inside dashboard fragments
      document
        .querySelectorAll("#toast-container")
        .forEach((el) => el.remove());

      c = document.createElement("div");
      c.id = "toast-container";
      c.className =
        "fixed top-6 right-6 z-[9999] space-y-3 pointer-events-none";
      document.body.appendChild(c);
    }

    const t = document.createElement("div");
    t.className =
      "p-4 rounded-lg shadow-2xl text-white max-w-sm pointer-events-auto transition-all duration-300 ease-out transform translate-x-0 opacity-100 " +
      (type === "success" ? "bg-green-600" : "bg-red-600");
    t.innerText = message;
    c.appendChild(t);

    // Slide out and fade out animation
    setTimeout(() => {
      t.style.opacity = "0";
      t.style.transform = "translateX(150%)";
      setTimeout(() => t.remove(), 300);
    }, 3500);
  }

  // Handles native browser back/forward buttons for seamless SPA history navigation
  window.addEventListener("popstate", function () {
    const p = new URLSearchParams(window.location.search);
    loadContent(p.get("page") || "welcome");
  });

  // Triggers the initial page load based on the current URL parameters
  const p = new URLSearchParams(window.location.search);
  loadContent(p.get("page") || "welcome");

  // Initialize unread count polling
  updateUnreadBadge();
  setInterval(updateUnreadBadge, 30000);
});
