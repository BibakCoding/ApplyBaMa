// static/js/pages/dashboard.js

document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarClose = document.getElementById('sidebarClose');
    const contentContainer = document.getElementById('dashboard-content');
    const navLinks = document.querySelectorAll('.nav-link');

    // Mobile Sidebar Toggle
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.add('open');
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        });
    }

    if (sidebarClose) {
        sidebarClose.addEventListener('click', closeSidebar);
    }

    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    // Load Content Function (Global so fragments can use it)
    window.loadContent = function(page, params = '') {
        const queryString = params ? `?${params}` : '';
        const url = window.AppConfig.urls.dashboardContent.replace('PAGE_PLACEHOLDER', page) + queryString;

        // Show loading state
        contentContainer.innerHTML = `
            <div class="content-loading">
                <div class="spinner"></div>
                <p>${window.AppConfig.translations.loadingContent}</p>
            </div>
        `;

        // Fetch the content
        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.text();
        })
        .then(html => {
            contentContainer.innerHTML = html;

            // Update active nav link
            navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('data-page') === page) {
                    link.classList.add('active');
                }
            });

            // Close mobile sidebar if open
            if (window.innerWidth < 1024) {
                closeSidebar();
            }

            // Update browser URL without reload (History API)
            window.history.pushState({ page: page }, '', `/dashboard/${page}${queryString}`);
        })
        .catch(error => {
            contentContainer.innerHTML = `
                <div class="text-center py-12">
                    <i class="fas fa-exclamation-triangle text-4xl text-red-400 mb-4"></i>
                    <h2 class="text-xl font-bold text-gray-800 mb-2">${window.AppConfig.translations.loadingError}</h2>
                    <p class="text-gray-500 mb-4">${window.AppConfig.translations.errorSupport}</p>
                    <button onclick="window.location.reload()" class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition">
                        ${window.AppConfig.translations.reloadPage}
                    </button>
                </div>
            `;
            console.error('Error loading content:', error);
        });
    };

    // Navigation Link Click Handlers
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = this.getAttribute('data-page');
            loadContent(page);
        });
    });

    // Handle browser back/forward buttons
    window.addEventListener('popstate', function(e) {
        if (e.state && e.state.page) {
            loadContent(e.state.page);
        }
    });

    // Load default page (welcome) if no state exists
    if (!window.history.state || !window.history.state.page) {
        loadContent('welcome');
    }
});
