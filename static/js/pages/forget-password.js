// forget-password.js
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('forgetForm');
    const notyf = new Notyf({duration: 3000, dismissible: true, position: {x: 'right', y: 'top'}});
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
                notyf.success(data.message);
                // Optionally redirect after a delay
                setTimeout(() => window.location.href = data.redirect || '{% url "main" %}', 4000);
            } else {
                // Show field errors or non-field errors
                if (data.errors && data.errors.email) {
                    emailError.textContent = data.errors.email[0].message;
                    emailError.classList.remove('hidden');
                }
                if (data.errors && data.errors.__all__) {
                    data.errors.__all__.forEach(err => notyf.error(err.message));
                }
            }
        } catch (err) {
            notyf.error('{{ _("An unexpected error occurred.") }}');
            console.error(err);
        }
    });
});
