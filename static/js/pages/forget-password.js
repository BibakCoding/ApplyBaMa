// forget-password.js
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('forgetForm');
    // Toasts come from the single notifier configured in base.html.
    const emailInput = document.getElementById('id_email');
    const emailError = document.getElementById('emailError');

    form.addEventListener('submit', async e => {
        e.preventDefault();
        emailError.textContent = '';
        emailError.classList.add('hidden');

        const payload = new FormData(form);

        try {
            const res = await fetch(form.action || window.location.href, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': window.CSRF_TOKEN,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: payload
            });

            const data = await res.json();

            if (res.ok && data.success) {
                window.notify(data.message, 'success');
                // The fallback comes from the form's data attribute: this file is
                // served as a static asset, so a Django url tag written here
                // would be delivered to the browser as literal text.
                setTimeout(() => window.location.href = data.redirect || form.dataset.redirect || '/', 4000);
            } else {
                // Show field errors or non-field errors
                if (data.errors && data.errors.email) {
                    emailError.textContent = data.errors.email[0].message;
                    emailError.classList.remove('hidden');
                }
                if (data.errors && data.errors.__all__) {
                    data.errors.__all__.forEach(err => window.notify(err.message, 'error'));
                }
            }
        } catch (err) {
            window.notify(
                (window.I18N && window.I18N.unexpectedError) || "An unexpected error occurred.",
                'error'
            );
            console.error(err);
        }
    });
});
