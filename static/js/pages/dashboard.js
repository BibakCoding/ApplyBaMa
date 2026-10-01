// static/js/pages/dashboard.js
document.addEventListener("DOMContentLoaded", function () {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("overlay");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const sidebarClose = document.getElementById("sidebarClose");
  const contentContainer = document.getElementById("dashboard-content");
  const navLinks = document.querySelectorAll(".nav-link");

  // Set when a realtime event wants the "My Notifications" fragment refreshed
  // while its detail modal is open; closeNotificationModal runs it on close.
  let myNotificationsRefreshPending = false;

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

    // Typing in a search box re-renders the whole fragment (the debounced
    // input handler calls loadContent), which would otherwise drop the field
    // and its caret mid-word. Elements opt in with data-restore-focus="key"
    // so the caret returns to the same box after the reload.
    const focusKey =
      document.activeElement instanceof HTMLElement
        ? document.activeElement.getAttribute("data-restore-focus")
        : null;
    contentContainer.innerHTML =
      '<div class="content-loading"><div class="spinner"></div><p>Loading...</p></div>';

    fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((r) => {
        // An expired session must not surface as "Error loading content": the
        // shared handler hands the visitor to the login form with ?next=.
        if (r.status === 401) {
          window.ApplyBaMa.handleAuthExpired();
          throw new Error("Auth expired");
        }
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

        // A fresh fragment has nothing left to refresh (see
        // myNotificationsRefreshPending above).
        myNotificationsRefreshPending = false;

        // Initialize page-specific logic after the new DOM elements are injected
        initProfileScripts();
        initSearchAutocomplete();
        initProgramAutocomplete();
        initNotificationsScripts();
        initMyNotificationsScripts();
        initAgentRequestScripts();
        // pages/chat.js owns its fragment's wiring (it is loaded with the
        // shell, so it cannot bind to elements that do not exist yet).
        if (typeof window.initChatScripts === "function") window.initChatScripts();

        // Update the browser's address bar to reflect the current SPA state
        const cleanParams = params.replace(/^\?/, "");
        const newUrl =
          window.location.pathname +
          "?page=" +
          page +
          (cleanParams ? "&" + cleanParams : "");
        window.history.pushState({ page: page }, "", newUrl);

        contentContainer.scrollTop = 0;

        // Hand focus back to the element that triggered the reload (the
        // notifications search box), so typing continues without a click.
        if (focusKey) {
          const restored = contentContainer.querySelector(
            '[data-restore-focus="' + focusKey + '"]',
          );
          if (restored) {
            restored.focus();
            try {
              const end = restored.value.length;
              restored.setSelectionRange(end, end);
            } catch (error) {
              // Input types without a caret (e.g. number) cannot restore it.
            }
          }
        }
      })
      .catch((err) => {
        // A 401 already sent the visitor to the login form (see above) and the
        // shell is on its way out: it must not flash an error box or spam the
        // console on the way.
        if (err instanceof Error && err.message === "Auth expired") return;
        contentContainer.innerHTML =
          '<div class="text-center py-12 text-red-500">Error loading content. Please refresh.</div>';
        console.error(err);
      });
  };

  // Single delegated listener for every SPA navigation trigger in the app:
  // sidebar links AND buttons inside fragments, which are injected with
  // innerHTML and therefore cannot be wired up individually. The markup only
  // declares the destination (`data-page`, plus optional `data-page-params`)
  // and this handler decides how to load it — no inline onclick handlers.
  document.addEventListener("click", function (e) {
    const target = e.target instanceof Element ? e.target : null;
    if (!target) return;

    // Modal open/close triggers stay declarative too.
    const modalTrigger = target.closest("[data-modal-open], [data-modal-close]");
    if (modalTrigger) {
      const isOpen = modalTrigger.hasAttribute("data-modal-open");
      const modalId = modalTrigger.getAttribute(
        isOpen ? "data-modal-open" : "data-modal-close"
      );
      const dialog = modalId ? document.getElementById(modalId) : null;
      if (dialog) dialog.classList.toggle("hidden", !isOpen);
      return;
    }

    // Any click inside the sidebar (including a link without data-page, such as
    // the admin panel shortcut) means the mobile drawer should not stay open.
    if (target.closest("#sidebar")) closeSidebar();

    const trigger = target.closest("[data-page]");
    if (!trigger) return;

    e.preventDefault();
    // A "Go" button inside the notification modal navigates away; without this
    // the modal would stay layered over the page that just loaded.
    if (target.closest(".notification-go-btn")) closeNotificationModal();
    loadContent(
      trigger.getAttribute("data-page"),
      trigger.getAttribute("data-page-params") || ""
    );
  });

  // Card-style triggers are div/span elements carrying role="button" (a card
  // cannot be wrapped in a <button> without breaking its layout), so they need
  // Enter/Space activation to be reachable from the keyboard.
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
    const target = e.target instanceof Element ? e.target : null;
    if (!target) return;
    if (!target.matches('[role="button"][data-page]')) return;
    e.preventDefault();
    target.click();
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
    } else if (form.id === "editNotificationForm") {
      e.preventDefault();
      handleEditNotification(form);
    } else if (form.id === "goToPageForm") {
      e.preventDefault();
      handleGoToPage(form);
    } else if (form.id === "notifSearchForm") {
      e.preventDefault();
      const term = form.querySelector("input[name=q]").value.trim();
      loadContent(form.dataset.section || "my_notifications", term ? "q=" + encodeURIComponent(term) : "");
    }
  });

  // Sort selects carry .filter-auto-submit and apply on change: sorting is a
  // view concern, not a filter that needs a second click to confirm. Delegated
  // like the submit listener above, so it keeps working on freshly injected
  // fragments.
  contentContainer.addEventListener("change", function (e) {
    const select = e.target.closest("select.filter-auto-submit");
    if (!select) return;
    applySortLabel(select);
    const form = select.closest("form");
    if (!form) return;
    if (form.id === "uniFilterForm" || form.id === "progFilterForm") {
      handleFilterSubmit(form);
    }
  });

  // Global event delegation for dynamic click actions (password toggles, apply buttons, etc.)
  contentContainer.addEventListener("click", function (e) {
    // Representation requests: accept/decline what I received, withdraw what I
    // sent, copy my own ID. Declarative in the markup (data-request-*,
    // .copy-id-btn), handled here so the freshly injected fragment needs no
    // wiring of its own.
    const respondBtn = e.target.closest("[data-request-respond]");
    if (respondBtn) {
      respondRequest(respondBtn);
      return;
    }
    const withdrawBtn = e.target.closest("[data-request-cancel]");
    if (withdrawBtn) {
      withdrawRequest(withdrawBtn);
      return;
    }
    const copyIdBtn = e.target.closest(".copy-id-btn");
    if (copyIdBtn) {
      copyPublicId(copyIdBtn);
      return;
    }

    // Email verification escape hatches (read-only mode banner + profile page)
    if (
      e.target.closest("#resend-email-verification") ||
      e.target.closest("#cancel-email-change")
    ) {
      handleEmailVerificationAction(e.target);
      return;
    }

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

    // Copy the generated temporary password into the clipboard. The styles for
    // the acknowledgement (.copy-pwd-btn.copied) already existed; only this
    // handler was missing, so the button did nothing at all.
    const copyPwdBtn = e.target.closest("#copyPwdBtn");
    if (copyPwdBtn) copyTemporaryPassword(copyPwdBtn);

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

    // Edit Notification Modal Controls
    if (e.target.closest(".edit-notif-btn")) {
        const btn = e.target.closest(".edit-notif-btn");
        const id = btn.dataset.id;
        document.getElementById("editNotifId").value = id;
        document.getElementById("editNotifTitle").value = btn.dataset.title;
        document.getElementById("editNotifMessage").value = btn.dataset.message;
        document.getElementById("editNotifType").value = btn.dataset.type;

        document.getElementById("editNotifModal").classList.remove("hidden");

        // Fetch current recipients to populate the edit modal
        fetch(window.AppConfig.urls.getNotifRecipients + id + "/", {
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                let initialSelected = new Map();
                data.users.forEach(u => {
                    initialSelected.set(u.id.toString(), { username: u.username, full_name: u.full_name });
                });
                initNotificationsScripts({
                    searchInputId: "editUserSearchInput",
                    listContainerId: "editUserListContainer",
                    selectedListId: "editSelectedUsersList",
                    userIdsInputId: "editUserIdsInput",
                    initialSelected: initialSelected
                });
            }
        });
    }
    if (e.target.id === "closeEditModalBtn" || e.target.closest("#closeEditModalBtn")) {
        document.getElementById("editNotifModal").classList.add("hidden");
    }
    if (e.target.id === "editNotifModal") {
        document.getElementById("editNotifModal").classList.add("hidden");
    }
  });

  // --- Temporary password: copy, then acknowledge it on the button ---------
  // The copy button shows an icon and nothing else, so its *state* has to carry
  // the message: the check icon, the green `.copied` tint (existing CSS in
  // pages/dashboard.css), and the title/aria-label the fragment renders for that
  // state. Static JS is never rendered as a template, so those two translated
  // strings arrive as data- attributes on the button.
  let copyPwdStateTimer = null;

  function setCopyPwdButtonState(button, copied) {
    const label = copied ? button.dataset.copiedTitle : button.dataset.copyTitle;
    const icon = button.querySelector("i");

    button.classList.toggle("copied", copied);
    if (icon) {
      icon.classList.replace(
        copied ? "fa-copy" : "fa-check",
        copied ? "fa-check" : "fa-copy",
      );
    }
    if (label) {
      button.title = label;
      button.setAttribute("aria-label", label);
    }
  }

  function copyTemporaryPassword(button) {
    const wrapper = button.closest(".password-wrapper");
    const input = wrapper
      ? wrapper.querySelector('input[name="password"]')
      : null;
    if (!input || !input.value) return;

    const acknowledge = () => {
      setCopyPwdButtonState(button, true);
      clearTimeout(copyPwdStateTimer);
      copyPwdStateTimer = setTimeout(
        () => setCopyPwdButtonState(button, false),
        1800,
      );
    };

    // clipboard.writeText needs a secure context (https, or localhost in dev).
    // Over plain http on a LAN it is undefined, and silently doing nothing is
    // exactly the bug this fixes — so fall back to selecting the field, which
    // also shows the user what was copied.
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(input.value).then(acknowledge, () => {
        if (selectAndCopy(input)) acknowledge();
      });
      return;
    }
    if (selectAndCopy(input)) acknowledge();
  }

  function selectAndCopy(input) {
    input.select();
    try {
      return document.execCommand("copy");
    } catch (err) {
      return false;
    }
  }

  // Initializes specific UI components (like dropdowns and phone inputs) when a new fragment loads
  function initProfileScripts() {
    const mobileInput = document.getElementById("id_mobile");
    let iti = null;
    if (mobileInput && window.intlTelInput) {
      iti = window.intlTelInput(mobileInput, {
        utilsScript: window.AppConfig.staticUrl + "vendor/intl-tel-input/js/utils.js",
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

        fetch(
          `${window.AppConfig.urls.getCities || "/dashboard/get-cities/"}?country_id=${this.value}`,
          { headers: { "X-Requested-With": "XMLHttpRequest" } },
        )
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
                  // bubbles: the filter forms are handled by the delegated
                  // submit listener on contentContainer, so a non-bubbling
                  // event reached nobody and the suggestion did nothing.
                  form.dispatchEvent(
                    new Event("submit", { cancelable: true, bubbles: true }),
                  );
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
      fetch(
        `${window.AppConfig.urls.programsSearch || "/dashboard/programs-search/"}?q=${encodeURIComponent(q || "")}`,
        { headers: { "X-Requested-With": "XMLHttpRequest" } },
      )
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

  function initNotificationsScripts(config = {}) {
    const searchInputId = config.searchInputId || "userSearchInput";
    const listContainerId = config.listContainerId || "userListContainer";
    const selectedListId = config.selectedListId || "selectedUsersList";
    const userIdsInputId = config.userIdsInputId || "userIdsInput";
    const initialSelected = config.initialSelected || new Map();

    const searchInput = document.getElementById(searchInputId);
    const userListContainer = document.getElementById(listContainerId);
    const selectedList = document.getElementById(selectedListId);
    const userIdsInput = document.getElementById(userIdsInputId);

    if (!userListContainer) return;

    let allUsersData = { default: [], company: [], agent: [] };
    let selectedUsers = new Map(initialSelected);

    const fetchAndRenderUsers = (q = "") => {
        fetch(`${window.AppConfig.urls.searchUsers}?q=${encodeURIComponent(q)}`, {
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
        .then(r => r.json())
        .then(data => {
            allUsersData = data;
            renderUserList();
        });
    };

    const renderUserList = () => {
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : "";
        userListContainer.innerHTML = "";

        const groups = [
            { key: "default", label: "Students (Default)", color: "blue" },
            { key: "company", label: "Company Users", color: "purple" },
            { key: "agent", label: "Agents", color: "green" }
        ];

        let filteredData = {};
        let totalFiltered = 0;
        for (let g of groups) {
            let users = (allUsersData[g.key] || []).filter(u =>
                !searchTerm ||
                u.username.toLowerCase().includes(searchTerm) ||
                (u.full_name && u.full_name.toLowerCase().includes(searchTerm))
            );
            filteredData[g.key] = users;
            totalFiltered += users.length;
        }

        if (totalFiltered === 0) {
            userListContainer.innerHTML = '<p class="text-sm text-gray-500 p-2">No users found.</p>';
            return;
        }

        // Master "All Users" header
        const allUsersHeader = document.createElement("div");
        allUsersHeader.className = "flex items-center p-2 bg-gray-200 rounded-t font-semibold text-gray-800 border-b";

        const masterCb = document.createElement("input");
        masterCb.type = "checkbox";
        masterCb.className = "mr-3 h-4 w-4 text-[#1E3A8A] rounded";
        masterCb.id = "masterSelectAll_" + listContainerId;

        let allVisibleIds = [];
        for(let k in filteredData) filteredData[k].forEach(u => allVisibleIds.push(u.id.toString()));
        masterCb.checked = allVisibleIds.length > 0 && allVisibleIds.every(id => selectedUsers.has(id));
        masterCb.indeterminate = !masterCb.checked && allVisibleIds.some(id => selectedUsers.has(id));

        masterCb.onchange = () => {
            if (masterCb.checked) {
                allVisibleIds.forEach(id => {
                    let u = findUserById(id);
                    if(u) selectedUsers.set(id, u);
                });
            } else {
                allVisibleIds.forEach(id => selectedUsers.delete(id));
            }
            updateSelectedUI();
            renderUserList();
        };

        const masterLabel = document.createElement("label");
        masterLabel.htmlFor = masterCb.id;
        masterLabel.className = "cursor-pointer flex-1";
        masterLabel.textContent = "Select All Users";

        const masterCount = document.createElement("span");
        masterCount.className = "text-sm font-normal text-gray-500";
        masterCount.textContent = `(${totalFiltered} users)`;

        allUsersHeader.appendChild(masterCb);
        allUsersHeader.appendChild(masterLabel);
        allUsersHeader.appendChild(masterCount);
        userListContainer.appendChild(allUsersHeader);

        groups.forEach(g => {
            if (filteredData[g.key].length === 0) return;

            const groupDiv = document.createElement("div");
            groupDiv.className = "border-b last:border-b-0";

            const groupHeader = document.createElement("div");
            groupHeader.className = `flex items-center p-2 bg-${g.color}-50 hover:bg-${g.color}-100 transition-colors`;

            const groupCb = document.createElement("input");
            groupCb.type = "checkbox";
            groupCb.className = `group-cb mr-3 h-4 w-4 text-${g.color}-600 rounded`;
            groupCb.dataset.group = g.key;

            let groupIds = filteredData[g.key].map(u => u.id.toString());
            groupCb.checked = groupIds.every(id => selectedUsers.has(id));
            groupCb.indeterminate = !groupCb.checked && groupIds.some(id => selectedUsers.has(id));

            groupCb.onchange = () => {
                if (groupCb.checked) {
                    groupIds.forEach(id => {
                        let u = findUserById(id);
                        if(u) selectedUsers.set(id, u);
                    });
                } else {
                    groupIds.forEach(id => selectedUsers.delete(id));
                }
                updateSelectedUI();
                renderUserList();
            };

            const groupLabel = document.createElement("label");
            groupLabel.className = "font-medium text-gray-700 cursor-pointer flex-1";
            groupLabel.textContent = g.label;

            groupHeader.appendChild(groupCb);
            groupHeader.appendChild(groupLabel);
            groupDiv.appendChild(groupHeader);

            const userList = document.createElement("div");
            userList.className = "pl-8 pr-2 py-1 space-y-1";

            filteredData[g.key].forEach(user => {
                const userDiv = document.createElement("div");
                userDiv.className = "flex items-center p-1 hover:bg-gray-50 rounded user-row visible";

                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.className = "user-checkbox mr-2 h-4 w-4 text-gray-600 rounded visible";
                cb.value = user.id;
                cb.dataset.username = user.username;
                cb.dataset.fullname = user.full_name || "";
                cb.checked = selectedUsers.has(user.id.toString());

                cb.onchange = () => {
                    if (cb.checked) {
                        selectedUsers.set(user.id.toString(), { username: user.username, full_name: user.full_name });
                    } else {
                        selectedUsers.delete(user.id.toString());
                    }
                    updateSelectedUI();
                    renderUserList();
                };

                const label = document.createElement("label");
                label.className = "text-sm text-gray-800 cursor-pointer flex-1";
                label.innerHTML = `<span class="font-medium">${user.username}</span> ${user.full_name ? `<span class="text-gray-500 text-xs">(${user.full_name})</span>` : ""}`;

                userDiv.appendChild(cb);
                userDiv.appendChild(label);
                userList.appendChild(userDiv);
            });

            groupDiv.appendChild(userList);
            userListContainer.appendChild(groupDiv);
        });
    };

    const findUserById = (id) => {
        for (let key in allUsersData) {
            let u = allUsersData[key].find(x => x.id.toString() === id);
            if (u) return { username: u.username, full_name: u.full_name };
        }
        return null;
    };

    const updateSelectedUI = () => {
        userIdsInput.value = Array.from(selectedUsers.keys()).join(",");
        selectedList.innerHTML = "";
        if (selectedUsers.size === 0) {
            selectedList.innerHTML = '<span class="text-sm text-gray-400">No users selected.</span>';
            return;
        }
        selectedUsers.forEach((userData, id) => {
            const chip = document.createElement("span");
            chip.className = "px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm flex items-center space-x-2";
            const span = document.createElement("span");
            span.textContent = userData.full_name || userData.username;
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "text-blue-600 hover:text-red-600";
            btn.innerHTML = '<i class="fas fa-times"></i>';
            btn.onclick = () => {
                selectedUsers.delete(id);
                updateSelectedUI();
                renderUserList();
            };
            chip.appendChild(span);
            chip.appendChild(btn);
            selectedList.appendChild(chip);
        });
    };

    if (searchInput) {
        let timeout;
        searchInput.addEventListener("input", function () {
            clearTimeout(timeout);
            const q = this.value;
            timeout = setTimeout(() => {
                fetchAndRenderUsers(q);
            }, 300);
        });
    }

    // Initial load
    fetchAndRenderUsers();
    updateSelectedUI();
  }

  // The detail modal lives in the dashboard SHELL (main.html), so a fragment
  // re-render can never delete it, and it centres on the viewport, not on the
  // page. These helpers keep every open/close path in one place; closing also
  // runs any fragment refresh that was deferred while the modal was open.
  function markNotificationItemRead(item) {
    const dot = item.querySelector(".w-3.h-3.bg-blue-600");
    if (dot) dot.remove();
    item.classList.remove("bg-blue-50", "border-blue-200");
    item.classList.add("bg-gray-50", "border-gray-200");
  }

  function isNotificationModalOpen() {
    const modal = document.getElementById("notificationModal");
    return !!modal && !modal.classList.contains("hidden");
  }

  function closeNotificationModal() {
    const modal = document.getElementById("notificationModal");
    if (modal) modal.classList.add("hidden");
    if (myNotificationsRefreshPending) {
      myNotificationsRefreshPending = false;
      loadContent("my_notifications");
    }
  }

  function showNotificationModal(contentHtml) {
    const modal = document.getElementById("notificationModal");
    if (!modal) return;
    document.getElementById("modalContent").innerHTML = contentHtml;
    modal.classList.remove("hidden");
  }

  function notificationTypeBadge(type) {
    const palette = {
      success: "bg-green-100 text-green-800",
      warning: "bg-yellow-100 text-yellow-800",
      error: "bg-red-100 text-red-800",
      info: "bg-blue-100 text-blue-800",
    };
    const label = { success: "Success", warning: "Warning", error: "Error", info: "Info" }[type] || "Reminder";
    return `<span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${palette[type] || "bg-gray-100 text-gray-800"}">${label}</span>`;
  }

  // Escape closes the shell modal no matter which fragment is open.
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isNotificationModalOpen()) closeNotificationModal();
  });

  function initMyNotificationsScripts() {
    const modal = document.getElementById("notificationModal");
    const closeModalBtn = document.getElementById("closeModalBtn");
    const markAllBtn = document.getElementById("markAllReadBtn");
    // Resolved before the modal guard below, because the search box is wired
    // from the fragment, not from the shell modal.
    const searchForm = document.getElementById("notifSearchForm");

    if (!modal) return;

    // A row may carry an action button (notification.action_url — e.g. a
    // representation request links to the Requests page). The delegated
    // data-page listener navigates; this row handler must stand aside, or the
    // modal would open on top of the page the button just loaded.
    const isActionButton = (node) => !!node.closest("[data-page]");

    // ONE click does everything: the modal opens at once with the row's own
    // text (zero waiting), then the read is recorded. Filling the modal from
    // the server response would need a round trip before anything appeared —
    // which is exactly the "second click" behaviour this replaces.
    document.querySelectorAll(".notification-item").forEach((item) => {
      item.addEventListener("click", function (event) {
        if (isActionButton(event.target)) return;
        const id = this.dataset.id;
        const title = this.querySelector("h3");
        const message = this.querySelector("p.text-gray-600");
        const dateText = [...this.querySelectorAll("p")].find((p) =>
          p.querySelector(".fa-clock"),
        );

        showNotificationModal(`
          <div class="mb-4" id="notificationModalType"></div>
          <h3 id="notificationModalTitle" class="text-xl font-bold text-gray-900 mb-2">${title ? title.textContent : ""}</h3>
          <p class="text-gray-600 mb-4 whitespace-pre-wrap">${message ? message.textContent : ""}</p>
          <p class="text-sm text-gray-500"><i class="far fa-clock mr-1"></i>${dateText ? dateText.textContent.trim() : ""}</p>
        `);

        // The list shows a truncated summary; replace it with the full body.
        // If anything goes wrong the modal stays open with the summary text.
        fetch(`${window.AppConfig.urls.notificationDetail || "/dashboard/notifications/detail/"}${id}/`, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
        })
          .then((r) => r.json())
          .then((data) => {
            if (!data.success || !isNotificationModalOpen()) return;
            // The deep link, when the notification carries one: clicking it
            // navigates the SPA (data-page) and closes the modal first.
            const actionHtml = data.action_url
              ? `<button type="button" data-page="${data.action_url}" class="notification-go-btn mt-4 px-4 py-2 text-sm font-semibold text-white bg-[var(--ab-primary)] rounded-lg hover:opacity-90 transition">${window.I18N.notificationGo} <i class="fas fa-arrow-right ml-1"></i></button>`
              : "";
            document.getElementById("modalContent").innerHTML = `
              <div class="mb-4">${notificationTypeBadge(data.type)}</div>
              <h3 id="notificationModalTitle" class="text-xl font-bold text-gray-900 mb-2">${data.title}</h3>
              <p class="text-gray-600 mb-4 whitespace-pre-wrap">${data.message}</p>
              <p class="text-sm text-gray-500"><i class="far fa-clock mr-1"></i>${data.date}</p>
              ${actionHtml}
            `;
          })
          .catch(() => {});

        // Record the read; the server pushes notifications.read back, which
        // realtime.js turns into the badge move in every tab, and
        // applyReadEvent below re-styles this row in place.
        // AppConfig, not a literal path: the SPA lives under a language prefix
        // (/en/dashboard/...), so "/dashboard/..." answers 302 and a POST
        // follows that redirect as a GET -- the write never happens.
        fetch(`${window.AppConfig.urls.markRead || "/dashboard/notifications/mark-read/"}${id}/`, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken":
              window.CSRF_TOKEN ||
              (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value ||
              "",
          },
        }).catch(() => {});

        markNotificationItemRead(this);
      });
    });

    if (closeModalBtn) {
      closeModalBtn.addEventListener("click", closeNotificationModal);
    }

    if (searchForm) {
      // Enter submits (delegated handler below); typing searches after a short
      // pause. The input re-renders the whole fragment server-side, so the
      // term is passed back through loadContent and restored into the box.
      let searchTimer;
      searchForm.querySelector("input[name=q]").addEventListener("input", function () {
        clearTimeout(searchTimer);
        const term = this.value;
        searchTimer = setTimeout(() => {
          // data-section matches the form's own fragment (same value as the
          // delegated submit handler uses below).
          loadContent(
            searchForm.dataset.section || "my_notifications",
            "q=" + encodeURIComponent(term),
          );
        }, 350);
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
              // No reload: the server pushes notifications.read for this
              // action, and applyReadEvent re-styles every row in place.
            }
          });
      });
    }
  }

  // --- Representation requests -------------------------------------------
  // The Requests fragment and the "Add by ID" dialog in My Students. Every
  // POST goes through core.agent_requests on the server, which owns the rules
  // (no self-requests, one live request per pair, target-only answers); the
  // code here only collects input and reports the answer.

  function postRequestAction(url, body, button, reloadPage) {
    if (button) button.disabled = true;
    return fetch(url, {
      method: "POST",
      body,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": window.ApplyBaMa.getCsrfToken(),
      },
    })
      .then((r) => r.json())
      .then((data) => {
        showToast(data.message || window.I18N.unexpectedError, data.success ? "success" : "error");
        if (data.success) {
          loadContent(reloadPage || "requests");
        } else if (button) {
          button.disabled = false;
        }
      })
      .catch(() => {
        if (button) button.disabled = false;
        showToast(window.I18N.unexpectedError, "error");
      });
  }

  function respondRequest(button) {
    const accept = button.getAttribute("data-request-respond") === "accept";
    if (!accept && !confirm(window.I18N.requestDeclineConfirm)) return;
    const body = new FormData();
    body.append("action", accept ? "accept" : "decline");
    postRequestAction(
      window.AppConfig.urls.agentRequestRespond +
        button.getAttribute("data-request-id") +
        "/",
      body,
      button,
      "requests",
    );
  }

  function withdrawRequest(button) {
    const body = new FormData();
    postRequestAction(
      window.AppConfig.urls.agentRequestCancel +
        button.getAttribute("data-request-cancel") +
        "/",
      body,
      button,
      "requests",
    );
  }

  // The public ID is shown as selectable text; this copies it without the
  // selection dance where the clipboard API is available. Same acknowledgement
  // as the temporary-password button (icon swap + .copied tint).
  function copyPublicId(button) {
    const value = button.getAttribute("data-copy-value") || "";
    if (!value) return;

    const acknowledge = () => {
      setCopyPwdButtonState(button, true);
      clearTimeout(copyPwdStateTimer);
      copyPwdStateTimer = setTimeout(
        () => setCopyPwdButtonState(button, false),
        1800,
      );
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(acknowledge, () => {
        if (copyThroughTextarea(value)) acknowledge();
      });
      return;
    }
    if (copyThroughTextarea(value)) acknowledge();
  }

  function copyThroughTextarea(value) {
    const holder = document.createElement("textarea");
    holder.value = value;
    holder.setAttribute("readonly", "readonly");
    // .sr-only (already in the bundle) keeps it out of sight while selectable:
    // execCommand("copy") needs a visible-to-the-DOM selection.
    holder.className = "sr-only";
    document.body.appendChild(holder);
    holder.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (err) {
      copied = false;
    }
    document.body.removeChild(holder);
    return copied;
  }

  function initAgentRequestScripts() {
    const idInput = document.getElementById("linkStudentIdInput");
    const searchBtn = document.getElementById("linkStudentSearchBtn");
    const resultBox = document.getElementById("linkStudentResult");
    const messageWrap = document.getElementById("linkStudentMessageWrap");
    const messageInput = document.getElementById("linkStudentMessage");
    const sendBtn = document.getElementById("linkStudentSendBtn");

    if (!idInput || !searchBtn || !resultBox || !sendBtn) return;

    const sendLabel = sendBtn.innerHTML;
    // Only a server-confirmed lookup may be sent: the ID in the box at send
    // time is not trusted, this value is.
    let confirmedId = null;
    let searchTimer;

    function resetResult() {
      confirmedId = null;
      resultBox.textContent = "";
      sendBtn.disabled = true;
      if (messageWrap) messageWrap.classList.add("hidden");
    }

    function renderMessage(text, isError) {
      const box = document.createElement("div");
      box.className =
        "text-sm rounded-lg p-3 " +
        (isError ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-800");
      box.textContent = text;
      resultBox.textContent = "";
      resultBox.appendChild(box);
    }

    function renderCandidate(candidate) {
      const card = document.createElement("div");
      card.className = "border border-gray-200 rounded-lg p-3";
      const name = document.createElement("p");
      name.className = "font-semibold text-gray-900";
      name.textContent = candidate.name;
      const meta = document.createElement("p");
      meta.className = "text-xs text-gray-600 mt-1";
      meta.textContent = [candidate.username, candidate.email, candidate.role]
        .filter(Boolean)
        .join(" · ");
      card.appendChild(name);
      card.appendChild(meta);
      resultBox.textContent = "";
      resultBox.appendChild(card);
    }

    function lookUp() {
      const value = (idInput.value || "").trim();
      if (!/^[0-9]{16}$/.test(value)) {
        resetResult();
        renderMessage(window.I18N.requestIdIncomplete, true);
        return;
      }
      searchBtn.disabled = true;
      fetch(
        window.AppConfig.urls.agentRequestSearch +
          "?public_id=" +
          encodeURIComponent(value),
        { headers: { "X-Requested-With": "XMLHttpRequest" } },
      )
        .then((r) => r.json())
        .then((data) => {
          if (!data.success || !data.found) {
            resetResult();
            renderMessage(data.message || window.I18N.unexpectedError, true);
            return;
          }
          renderCandidate(data.candidate);
          if (!data.can_send) {
            renderMessage(data.message, true);
            return;
          }
          confirmedId = value;
          sendBtn.disabled = false;
          if (messageWrap) messageWrap.classList.remove("hidden");
        })
        .catch(() => {
          resetResult();
          renderMessage(window.I18N.unexpectedError, true);
        })
        .finally(() => {
          searchBtn.disabled = false;
        });
    }

    searchBtn.addEventListener("click", lookUp);
    idInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        lookUp();
      }
    });
    // A pasted ID is looked up as soon as it is complete; typing is left alone
    // until the user asks (the button or Enter), so half-typed digits never
    // hit the endpoint.
    idInput.addEventListener("input", function () {
      resetResult();
      clearTimeout(searchTimer);
      const value = idInput.value.trim();
      if (!/^[0-9]{16}$/.test(value)) return;
      // Pasted or typed in full: look it up after a beat, so a fast typist does
      // not fire a request on the 16th digit of a still-changing value.
      searchTimer = setTimeout(lookUp, 250);
    });

    sendBtn.addEventListener("click", function () {
      if (!confirmedId) return;
      const body = new FormData();
      body.append("public_id", confirmedId);
      body.append("message", messageInput ? messageInput.value : "");
      sendBtn.disabled = true;
      sendBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin mr-2"></i>' + window.I18N.requestSending;
      fetch(window.AppConfig.urls.agentRequestSend, {
        method: "POST",
        body,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": window.ApplyBaMa.getCsrfToken(),
        },
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.success) {
            showToast(data.message || "", "success");
            const modal = document.getElementById("linkStudentModal");
            if (modal) modal.classList.add("hidden");
            loadContent("my_students");
            return;
          }
          showToast(data.message || window.I18N.unexpectedError, "error");
          sendBtn.disabled = false;
          sendBtn.innerHTML = sendLabel;
        })
        .catch(() => {
          showToast(window.I18N.unexpectedError, "error");
          sendBtn.disabled = false;
          sendBtn.innerHTML = sendLabel;
        });
    });

    // Reopening the dialog starts clean: the previous lookup (and its result)
    // must not be resendable by a second click.
    document
      .querySelectorAll('[data-modal-open="linkStudentModal"]')
      .forEach((trigger) =>
        trigger.addEventListener("click", function () {
          idInput.value = "";
          if (messageInput) messageInput.value = "";
          sendBtn.innerHTML = sendLabel;
          resetResult();
        }),
      );
  }

  function setRequestsBadge(count) {
    const badge = document.getElementById("requestsBadge");
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }

  function isRequestsOpen() {
    const params = new URLSearchParams(window.location.search);
    return params.get("page") === "requests";
  }

  document.addEventListener("ab:requests-refresh", function (event) {
    const pending = (event.detail || {}).pending;
    if (typeof pending === "number") setRequestsBadge(pending);
    // The page lists exactly these rows, so a change redraws it.
    if (isRequestsOpen()) loadContent("requests");
  });

  // --- Realtime notifications (WebSocket, see static/js/realtime.js) -------
  // realtime.js re-dispatches pushed server events as document CustomEvents.
  // The sidebar badge and toasts are handled there for every page; the
  // listeners below only keep the open "My Notifications" fragment fresh. No
  // polling: the socket is the source of truth.

  function isMyNotificationsOpen() {
    const params = new URLSearchParams(window.location.search);
    return params.get("page") === "my_notifications";
  }

  // A read change never needs a re-render: the rows are already rendered and
  // only their read styling changes, so it is applied in place. The detail
  // modal lives in the shell, so even a re-render could not close it any more —
  // but an in-place update is still smoother than redrawing the list. The
  // composer page ("notifications") is deliberately not touched: a re-render
  // would wipe the form the user is working in.
  function applyReadEvent(event) {
    if (!isMyNotificationsOpen()) return;
    const id = (event.detail || {}).id;
    if (id) {
      const item = document.querySelector(`.notification-item[data-id="${id}"]`);
      if (item) markNotificationItemRead(item);
      return;
    }
    // No id: "mark all as read", from this tab or another one.
    document.querySelectorAll(".notification-item").forEach(markNotificationItemRead);
  }

  document.addEventListener("ab:notifications-read", applyReadEvent);

  // A genuinely new notification needs new rows, so this one does reload the
  // fragment — but not while the modal is open, or the reload would take the
  // modal with it.
  document.addEventListener("ab:notification-new", function (event) {
    // A representation request also arrives as a notification; when the
    // Requests page is the open fragment it lists that row, so redraw it.
    if (isRequestsOpen() && (event.detail || {}).action_url === "requests") {
      loadContent("requests");
    }
    if (!isMyNotificationsOpen()) return;
    if (isNotificationModalOpen()) {
      myNotificationsRefreshPending = true;
      return;
    }
    loadContent("my_notifications");
  });

  // Chat: when the chat page is the open fragment, an agent/company adding a
  // student (or any thread-level refresh push) re-renders it. The badge and
  // toasts are handled by chat.js/realtime.js on every other page.
  document.addEventListener("ab:chat-event", function (event) {
    const type = (event.detail || {}).type;
    if (type === "chat.refresh" && isChatOpen()) loadContent("chat");
  });

  function isChatOpen() {
    const params = new URLSearchParams(window.location.search);
    return params.get("page") === "chat";
  }

  function handleSendNotification(form) {
    const formData = new FormData(form);
    const userIds = document.getElementById("userIdsInput").value;
    if (!userIds) {
      showToast("Please select at least one user.", "error");
      return;
    }
    // recipient_type is already set to "specific" in the hidden input

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
        btn.innerHTML = '<i class="fas fa-paper-plane mr-2"></i>Send';
        if (data.success) {
          showToast(data.message, "success");
          setTimeout(() => loadContent("notifications"), 500);
        } else {
          showToast(data.message || "Error sending notification.", "error");
        }
      });
  }

  function handleEditNotification(form) {
    const formData = new FormData(form);
    const id = formData.get("notif_id");
    formData.delete("notif_id");

    // Ensure user_ids is included even if empty
    const userIds = document.getElementById("editUserIdsInput").value;
    formData.set("user_ids", userIds);

    const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Updating...';

    fetch(window.AppConfig.urls.updateNotification + id + "/", {
      method: "POST",
      body: formData,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken
      }
    })
    .then(r => r.json())
    .then(data => {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save mr-2"></i>Update';
        if (data.success) {
            showToast(data.message, "success");
            document.getElementById("editNotifModal").classList.add("hidden");
            setTimeout(() => loadContent("notifications"), 500);
        } else {
            showToast(data.message || "Error updating notification.", "error");
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

  // The server renders option labels for the active language; when a sort
  // changes without a submit, its new label must still come from the same
  // translated set, so it is applied from window.I18N instead of being read
  // back out of the old DOM.
  function applySortLabel(select) {
    const labels = window.I18N && window.I18N.sortLabels;
    if (!labels) return;
    const value = select.value || "";
    if (labels[value]) {
      const option = select.selectedOptions[0];
      if (option) option.textContent = labels[value];
    }
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
      .then((r) => {
        if (window.ApplyBaMa.isAuthFailure(r))
          window.ApplyBaMa.handleAuthExpired();
        return r.json();
      })
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

  // Non-blocking toast. Delegates to the single notifier configured in
  // base.html so the dashboard shows exactly the same notifications (position,
  // colours, icons, durations) as every other page, instead of maintaining a
  // second, competing toast implementation.
  // Kept as a named function because it still has many call sites here.
  function showToast(message, type) {
    if (typeof window.notify === "function") {
      window.notify(message, type);
      return;
    }
    // Defensive fallback only: a missing notifier must never swallow a message
    // the user needs to see.
    console.log("[" + (type || "info") + "] " + message);
  }

  // Resend the verification email, or cancel a pending email change. Both
  // actions POST to their dashboard endpoint and reload the fragment on
  // success so the read-only banner reflects the new state immediately.
  function handleEmailVerificationAction(target) {
    const isResend = !!target.closest("#resend-email-verification");
    const urls = (window.AppConfig && window.AppConfig.urls) || {};
    const endpoint = isResend
      ? urls.resendEmailVerification
      : urls.cancelEmailChange;
    if (!endpoint) return;

    const btn = target.closest("button");
    if (btn) btn.disabled = true;

    fetch(endpoint, {
      method: "POST",
      headers: {
        "X-CSRFToken": window.ApplyBaMa.getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then((r) =>
        r.json().catch(() => ({})).then((data) => ({ status: r.status, data })),
      )
      .then(({ status, data }) => {
        if (data && data.success) {
          showToast(data.message, "success");
          // Reload the current fragment: the banner disappears once the
          // account is fully verified again.
          const params = new URLSearchParams(window.location.search);
          loadContent(params.get("page") || "welcome", "");
        } else {
          const msg =
            (data && data.errors && data.errors.join("\n")) ||
            (data && data.message) ||
            "Error";
          showToast(msg, "error");
          if (btn) btn.disabled = false;
        }
      })
      .catch(() => {
        showToast("Network error. Please try again.", "error");
        if (btn) btn.disabled = false;
      });
  }

  // Handles native browser back/forward buttons for seamless SPA history navigation
  window.addEventListener("popstate", function () {
    const p = new URLSearchParams(window.location.search);
    const page = p.get("page") || "welcome";
    p.delete("page");
    loadContent(page, p.toString());
  });

  // Triggers the initial page load based on the current URL parameters
  const p = new URLSearchParams(window.location.search);

  // Filters carried over from the home-page hero search are applied by the
  // server (dashboard_main redirects here with ?page=programs&country=…),
  // so the query string alone already describes the first page to load.
  const initialPage = p.get("page") || "welcome";
  p.delete("page");
  loadContent(initialPage, p.toString());

  // Initial badge value comes from the server once; afterwards the WebSocket
  // is the source of truth (realtime.js updates the badge on every push and
  // re-syncs it on reconnect), so the old 30-second polling interval is gone.
});
