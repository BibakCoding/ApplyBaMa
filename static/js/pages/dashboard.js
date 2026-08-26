// dashboard.js
document.addEventListener("DOMContentLoaded", () => {
    // Safely grab translations and URLs injected from the Django template
    const config = window.AppConfig || {};
    const urls = config.urls || {};
    const t = config.translations || {};

    // Fallbacks just in case
    const MSG_LOADING = t.loadingContent || "Loading content...";
    const MSG_ERROR = t.loadingError || "Loading Error";
    const MSG_SUPPORT = t.errorSupport || "Please try again or contact support";
    const MSG_RELOAD = t.reloadPage || "Reload Page";

    // Show notification function
    function showNotification(message, type = 'success') {
        if (typeof Notyf !== 'undefined') {
            const notyf = new Notyf({
                duration: 5000,
                dismissible: true,
                position: {x: 'right', y: 'top'}
            });

            if (type === 'success') {
                notyf.success(message);
            } else {
                notyf.error(message);
            }
        } else {
            console.log(`[${type}] ${message}`);
        }
    }

    // Sidebar toggle elements
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("overlay");
    const toggleBtn = document.getElementById("sidebarToggle");
    const sidebarClose = document.getElementById("sidebarClose");

    // Mobile detection
    const isMobile = () => window.innerWidth < 768;

    // Sidebar toggle functions
    const openSidebar = () => {
        sidebar.classList.remove("-translate-x-full");
        overlay.classList.remove("hidden");
    };

    const closeSidebar = () => {
        sidebar.classList.add("-translate-x-full");
        overlay.classList.add("hidden");
    };

    // Initialize sidebar state
    if (isMobile()) closeSidebar();

    // Event listeners for sidebar
    if (toggleBtn) toggleBtn.addEventListener("click", openSidebar);
    if (sidebarClose) sidebarClose.addEventListener("click", closeSidebar);
    if (overlay) overlay.addEventListener("click", closeSidebar);

    // Resize handler
    window.addEventListener("resize", () => {
        if (!isMobile()) {
            sidebar.classList.remove("-translate-x-full");
            overlay.classList.add("hidden");
        }
    });

    // Dashboard content loading
    const loadDashboardContent = (page) => {
        const contentArea = document.getElementById('dashboard-content');
        if (!contentArea) return;

        contentArea.innerHTML = `
            <div class="text-center py-16">
                <div class="inline-flex items-center justify-center bg-gray-200 rounded-full w-16 h-16 mb-4">
                    <i class="fas fa-spinner fa-spin text-2xl text-blue-500"></i>
                </div>
                <p class="text-lg font-medium text-gray-700">${MSG_LOADING}</p>
            </div>
        `;

        // Construct the URL safely using the injected template
        const targetUrl = (urls.dashboardContent || '').replace('PAGE_PLACEHOLDER', page);

        fetch(targetUrl)
            .then(response => {
                if (response.redirected) {
                    window.location.href = response.url;
                    return;
                }
                if (!response.ok) throw new Error('Network response was not ok');
                return response.text();
            })
            .then(html => {
                if (html !== undefined) {
                    contentArea.innerHTML = html;
                    history.pushState({page}, '', `?page=${page}`);

                    if (page === 'profile') {
                        initProfilePage();
                    }

                    // Set active link
                    document.querySelectorAll('.dashboard-link').forEach(link => {
                        // Remove active states (update these to match your theme if needed)
                        link.classList.remove('bg-blue-50', 'text-blue-700', 'ab-bg-primary-soft', 'ab-text-primary');
                    });
                    const activeLink = document.querySelector(`.dashboard-link[data-page="${page}"]`);
                    if (activeLink) {
                        // Apply active state
                        activeLink.classList.add('bg-blue-50', 'text-blue-700', 'ab-bg-primary-soft', 'ab-text-primary');
                    }
                }
            })
            .catch(error => {
                console.error('Error loading content:', error);
                contentArea.innerHTML = `
                    <div class="text-center py-16">
                        <div class="inline-flex items-center justify-center bg-red-100 rounded-full w-16 h-16 mb-4">
                            <i class="fas fa-exclamation-triangle text-2xl text-red-500"></i>
                        </div>
                        <h3 class="text-lg font-medium text-gray-900 mb-1">${MSG_ERROR}</h3>
                        <p class="text-gray-500">${MSG_SUPPORT}</p>
                        <button onclick="location.reload()" class="mt-4 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600">
                            ${MSG_RELOAD}
                        </button>
                    </div>
                `;
            });
    };

    // Add click handlers to dashboard links
    document.querySelectorAll('.dashboard-link').forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            loadDashboardContent(this.dataset.page);
            if (isMobile()) closeSidebar();
        });
    });

    // Handle browser history
    window.addEventListener('popstate', (event) => {
        if (event.state?.page) loadDashboardContent(event.state.page);
    });

    // Load initial content
    const urlParams = new URLSearchParams(window.location.search);
    loadDashboardContent(urlParams.get('page') || 'welcome');
});

// ------------------------------------------------------------
// Define initProfilePage() to wire up “Profile” fragment events
// ------------------------------------------------------------
function initProfilePage() {
    // 1) Toggle between view‐mode and edit‐mode
    const editBtn = document.getElementById("edit-toggle");
    const cancelBtn = document.getElementById("cancel-edit");
    const viewMode = document.getElementById("view-mode");
    const editMode = document.getElementById("edit-mode");

    if (editBtn) {
        editBtn.addEventListener("click", () => {
            if(viewMode) viewMode.classList.add("hidden");
            if(editMode) editMode.classList.remove("hidden");
        });
    }
    if (cancelBtn) {
        cancelBtn.addEventListener("click", () => {
            if(editMode) editMode.classList.add("hidden");
            if(viewMode) viewMode.classList.remove("hidden");
        });
    }

    // 2) Country → City AJAX
    const countrySelect = document.getElementById("id_country");
    const citySelect = document.getElementById("id_city");

    if (countrySelect && citySelect) {
        countrySelect.addEventListener("change", function () {
            const countryId = this.value;
            if (!countryId) {
                citySelect.innerHTML = '<option value="">— Select Country First —</option>';
                citySelect.disabled = true;
                return;
            }

            // We will use the Django URL reverse pattern here later,
            // but hardcoded relative path works if the API is standard.
            fetch(`/api/cities/?country_id=${countryId}`)
                .then((response) => {
                    if (!response.ok) throw new Error("Network response was not OK");
                    return response.json();
                })
                .then((data) => {
                    citySelect.disabled = false;
                    citySelect.innerHTML = '<option value="">— Select City —</option>';
                    data.forEach((item) => {
                        const opt = document.createElement("option");
                        opt.value = item.id;
                        opt.textContent = item.name;
                        citySelect.appendChild(opt);
                    });
                })
                .catch((error) => {
                    console.error("Error fetching cities:", error);
                });
        });

        // If editing and a country is already selected, populate cities immediately
        if (countrySelect.value) {
            countrySelect.dispatchEvent(new Event("change"));
        }
    }
}
