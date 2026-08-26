// login.js
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("loginForm");
    const notyf = new Notyf({
        duration: 4000,
        dismissible: true,
        position: {x: 'right', y: 'top'}
    });
    const nonFieldEl = document.getElementById("loginNonFieldErrors");


    // Password toggle
    document.querySelectorAll('.pwd-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const input = document.getElementById(btn.dataset.target);
            const icon = btn.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.replace('fa-eye', 'fa-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.replace('fa-eye-slash', 'fa-eye');
            }
        });
    });

    form.addEventListener("submit", async e => {
        e.preventDefault();
        nonFieldEl.innerHTML = "";
        document.querySelectorAll(".error-msg").forEach(el => el.remove());

        const data = new FormData(form);
        try {
            const res = await fetch(form.action, {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: data
            });

            if (!res.ok) throw res;
            const json = await res.json();
            notyf.success(json.message);
            setTimeout(() => window.location = json.redirect, 500);
        } catch (errResp) {
            // attempt JSON parse, else fallback
            let json;
            try {
                json = await errResp.json();
            } catch {
                notyf.error("{{ _('Unexpected server response.')|escapejs }}");
                console.error("Non-JSON response:", errResp);
                return;
            }

            const errs = json.errors || {};

            // Non-field errors
            if (errs.__all__) {
                errs.__all__.forEach(item => {
                    const p = document.createElement("p");
                    p.className = "mb-4 p-2 bg-red-100 border border-red-400 text-red-700 rounded error-msg";
                    p.innerText = item.message;
                    nonFieldEl.appendChild(p);
                    notyf.error(item.message);
                });
            }

            // Field errors
            Object.entries(errs).forEach(([field, fieldErrs]) => {
                if (field === "__all__") return;
                const input = document.getElementById(`id_${field}`);
                fieldErrs.forEach(item => {
                    const p = document.createElement("p");
                    p.className = "mt-1 text-sm text-red-500 error-msg";
                    p.innerText = item.message;
                    input.insertAdjacentElement("afterend", p);
                    const labelText = form.elements[field].labels[0].innerText;
                    notyf.error(`${labelText}: ${item.message}`);
                });
            });
        }
    });
});
