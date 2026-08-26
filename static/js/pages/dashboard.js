// static/js/pages/dashboard.js
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarClose = document.getElementById('sidebarClose');
    const contentContainer = document.getElementById('dashboard-content');
    const navLinks = document.querySelectorAll('.nav-link');

    // --- Sidebar Controls ---
    if (sidebarToggle) sidebarToggle.addEventListener('click', () => { sidebar.classList.add('open'); overlay.classList.add('active'); });
    if (sidebarClose) sidebarClose.addEventListener('click', closeSidebar);
    if (overlay) overlay.addEventListener('click', closeSidebar);

    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
    }

    // --- SPA Navigation ---
    window.loadContent = function(page, params = '') {
        const queryString = params ? (params.startsWith('?') ? params : `?${params}`) : '';
        const url = window.AppConfig.urls.dashboardContent.replace('PAGE_PLACEHOLDER', page) + queryString;

        contentContainer.innerHTML = `<div class="content-loading"><div class="spinner"></div><p>Loading...</p></div>`;

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(r => {
            if (!r.ok) throw new Error('Network error');
            return r.text();
        })
        .then(html => {
            contentContainer.innerHTML = html;

            // Update active nav link
            navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('data-page') === page) link.classList.add('active');
            });

            closeSidebar();

            // Update URL safely
            const newUrl = `${window.location.pathname}?page=${page}${params ? '&' + params.replace('?', '') : ''}`;
            window.history.pushState({ page }, '', newUrl);
        })
        .catch(error => {
            contentContainer.innerHTML = `<div class="text-center py-12 text-red-500">Error loading content. Please refresh.</div>`;
            console.error(error);
        });
    };

    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            loadContent(this.getAttribute('data-page'));
        });
    });

    // --- BULLETPROOF EVENT DELEGATION ---

    // 1. Catch ALL form submissions inside the dashboard
    contentContainer.addEventListener('submit', function(e) {
        const form = e.target.closest('form');
        if (!form) return;

        if (form.classList.contains('profile-form')) {
            e.preventDefault();
            handleProfileSubmit(form);
        } else if (form.id === 'uniFilterForm' || form.id === 'progFilterForm') {
            e.preventDefault();
            handleFilterSubmit(form);
        } else if (form.id === 'newAppForm' || form.id === 'addStudentForm') {
            e.preventDefault();
            handleJsonSubmit(form, true);
        } else if (form.classList.contains('delete-form') || form.classList.contains('step-form')) {
            e.preventDefault();
            handleJsonSubmit(form, false);
        }
    });

    // 2. Catch button clicks (like Generate Password)
    contentContainer.addEventListener('click', function(e) {
        if (e.target.id === 'generatePwdBtn' || e.target.closest('#generatePwdBtn')) {
            const genPwdUrl = window.AppConfig.urls.generatePassword || '/dashboard/generate-password/';
            fetch(genPwdUrl)
                .then(r => r.json())
                .then(data => {
                    const pwdInput = document.querySelector('input[name="password"]');
                    if (pwdInput) pwdInput.value = data.password;
                });
        }
    });

    // --- AJAX Handlers ---
    function handleProfileSubmit(form) {
        const formData = new FormData(form);
        const btn = form.querySelector('button[type="submit"]');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Saving...';

        fetch(form.action, { method: 'POST', body: formData, headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast(data.message, 'success');
                loadContent('profile'); // Reload fragment to show updated data
            } else {
                showToast(data.errors ? data.errors.join('\n') : 'Error', 'error');
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        });
    }

    function handleFilterSubmit(form) {
        const formData = new FormData(form);
        const params = new URLSearchParams(formData).toString();
        const page = form.id === 'uniFilterForm' ? 'universities' : 'programs';
        loadContent(page, params);
    }

    function handleJsonSubmit(form, isCreation) {
        if (form.classList.contains('delete-form')) {
            if (!confirm('Are you sure you want to delete this?')) return;
        }
        const formData = new FormData(form);
        fetch(form.action, { method: 'POST', body: formData, headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                showToast(data.message || 'Success', 'success');
                const currentPage = window.history.state ? window.history.state.page : 'my_applications';
                loadContent(data.redirect ? 'my_applications' : currentPage);
            } else {
                const errDiv = form.querySelector('#formErrors');
                if (errDiv && data.errors) {
                    errDiv.innerHTML = Object.entries(data.errors).map(([k,v]) => `<p>${k}: ${v.join(', ')}</p>`).join('');
                    errDiv.classList.remove('hidden');
                } else {
                    showToast(data.message || 'Error', 'error');
                }
            }
        });
    }

    function showToast(message, type) {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'fixed top-4 right-4 z-50 space-y-3';
            document.body.appendChild(container);
        }
        const toast = document.createElement('div');
        toast.className = `p-4 rounded-lg shadow-lg text-white z-50 transition-all ${type === 'success' ? 'bg-green-500' : 'bg-red-500'}`;
        toast.innerText = message;
        container.appendChild(toast);
        setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3000);
    }

    // Handle browser back/forward and page refresh
    window.addEventListener('popstate', function() {
        const urlParams = new URLSearchParams(window.location.search);
        loadContent(urlParams.get('page') || 'welcome');
    });

    // Initial load
    const urlParams = new URLSearchParams(window.location.search);
    loadContent(urlParams.get('page') || 'welcome');
});
