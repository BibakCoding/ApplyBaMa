// change-password.js
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('changeForm');
    // Toasts come from the single notifier configured in base.html.
    const fields = ['code', 'pw1', 'pw2'];

    form.addEventListener('submit', async e => {
        e.preventDefault();
        // clear errors
        fields.forEach(f => {
            const errP = document.getElementById(f + 'Error');
            errP.textContent = '';
            errP.classList.add('hidden');
        });

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
                setTimeout(() => window.location.href = data.redirect, 800);
            } else {
                // field errors
                Object.entries(data.errors || {}).forEach(([field, errs]) => {
                    if (field !== '__all__') {
                        const el = document.getElementById(field + 'Error');
                        el.textContent = errs[0].message;
                        el.classList.remove('hidden');
                    }
                });
                // non-field
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
