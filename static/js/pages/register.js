// register.js
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("registerForm");
    const notyf = new Notyf({
        duration: 10000, dismissible: true, position: {x: 'right', y: 'top'}
    });
    const nonFieldDiv = document.getElementById("nonFieldErrors");

    form.addEventListener("submit", async e => {
        e.preventDefault();
        // Clear previous inline errors
        document.querySelectorAll(".error-msg").forEach(el => el.remove());
        nonFieldDiv.innerHTML = "";

        const data = new FormData(form);
        try {
            const res = await fetch(form.action, {
                method: "POST",
                headers: {"X-Requested-With": "XMLHttpRequest"},
                body: data
            });
            if (!res.ok) throw res;
            const json = await res.json();
            window.location.href = json.redirect;
        } catch (errResponse) {
            const json = await errResponse.json();
            const errs = json.errors || {};

            // Handle non-field errors (__all__)
            if (errs.__all__) {
                errs.__all__.forEach(item => {
                    const p = document.createElement("p");
                    p.className = "mb-4 p-2 bg-red-100 border border-red-400 text-red-700 rounded error-msg";
                    p.innerText = item.message;
                    nonFieldDiv.appendChild(p);
                    notyf.error(item.message);
                });
            }

            // Field errors
            for (const [field, fieldErrs] of Object.entries(errs)) {
                if (field === "__all__") continue;
                const input = document.getElementById(`id_${field}`);
                fieldErrs.forEach(item => {
                    const p = document.createElement("p");
                    p.className = "mt-1 text-sm text-red-500 error-msg";
                    p.innerText = item.message;
                    input.insertAdjacentElement("afterend", p);
                    notyf.error(`${form.elements[field].labels[0].innerText}: ${item.message}`);
                });
            }
        }
    });
});
