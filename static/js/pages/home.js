// home.js
document.addEventListener("DOMContentLoaded", () => {
    // Mobile menu toggle
    const menuBtn = document.getElementById('menuBtn');
    const mobileNav = document.getElementById('mobileNav');
    if (menuBtn && mobileNav) {
        menuBtn.addEventListener('click', () => {
            mobileNav.classList.toggle('hidden');
        });
    }

    // Profile form handling
    function setupProfileForm() {
        // Toggle between view and edit modes
        const editToggle = document.getElementById('edit-toggle');
        const cancelEdit = document.getElementById('cancel-edit');
        const viewMode = document.getElementById('view-mode');
        const editMode = document.getElementById('edit-mode');

        if (editToggle) {
            editToggle.addEventListener('click', function () {
                viewMode.classList.add('hidden');
                editMode.classList.remove('hidden');
                this.classList.add('hidden');
            });
        }

        if (cancelEdit) {
            cancelEdit.addEventListener('click', function () {
                viewMode.classList.remove('hidden');
                editMode.classList.add('hidden');
                if (editToggle) editToggle.classList.remove('hidden');
            });
        }

        // Handle country-city dependency
        const countrySelect = document.getElementById('id_country');
        const citySelect = document.getElementById('id_city');

        if (countrySelect && citySelect) {
            countrySelect.addEventListener('change', function () {
                const countryId = this.value;
                if (countryId) {
                    fetch(`/api/cities/?country_id=${countryId}`)
                        .then(response => response.json())
                        .then(data => {
                            citySelect.innerHTML = '';

                            // Add default option
                            const defaultOption = document.createElement('option');
                            defaultOption.value = '';
                            defaultOption.textContent = '---------';
                            citySelect.appendChild(defaultOption);

                            // Add new options
                            data.forEach(city => {
                                const option = document.createElement('option');
                                option.value = city.id;
                                option.textContent = city.name;
                                citySelect.appendChild(option);
                            });
                        });
                } else {
                    citySelect.innerHTML = '<option value="">---------</option>';
                }
            });

            // Trigger change event if country is pre-selected
            if (countrySelect.value) {
                countrySelect.dispatchEvent(new Event('change'));
            }
        }

        // Handle form submission
        const profileForm = document.getElementById('profile-form');
        if (profileForm) {
            profileForm.addEventListener('submit', function (e) {
                e.preventDefault();

                const formData = new FormData(this);

                fetch("{% url 'profile_view' %}", {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // Success - reload profile content
                            loadDashboardContent('profile');
                            // Show success notification
                            showNotification(data.message, 'success');
                        } else if (data.form_html) {
                            // Update form with errors
                            const contentArea = document.getElementById('dashboard-content');
                            contentArea.innerHTML = data.form_html;
                            // Re-setup the form listeners
                            setupProfileForm();
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        showNotification('{% trans "An error occurred. Please try again." %}', 'error');
                    });
            });
        }
    }

    // Initialize profile form when loaded
    function initProfilePage() {
        if (document.getElementById('profile-form')) {
            setupProfileForm();
        }
    }

    // Show notification function
    function showNotification(message, type = 'success') {
        // Use your existing notification system (Notyf)
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
    }

    // Dashboard content loading code
    function loadDashboardContent(page) {
        const contentArea = document.getElementById('dashboard-content');
        if (!contentArea) return;

        // Show loading indicator
        contentArea.innerHTML = '<div class="text-center py-8">Loading...</div>';

        fetch(`/dashboard/${page}/`)
            .then(response => response.text())
            .then(html => {
                if (html) {
                    contentArea.innerHTML = html;

                    // Initialize profile page if needed
                    if (page === 'profile') {
                        initProfilePage();
                    }
                }
            })
            .catch(error => {
                console.error('Error loading content:', error);
                contentArea.innerHTML = '<div class="text-red-500 text-center py-8">Error loading content</div>';
            });
    }
});
