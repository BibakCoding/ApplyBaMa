// confirm-code.js
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('confirmForm');
    const notyf = new Notyf({duration: 4000, dismissible: true, position: {x: 'right', y: 'top'}});  // Notyf usage :contentReference[oaicite:5]{index=5}
    const nonField = document.getElementById('confirmNonFieldErrors');
    const inputs = Array.from({length: 6}, (_, i) => document.getElementById(`code${i + 1}`));

    // Auto-focus & collect code
    inputs.forEach((inp, idx) => {
        inp.addEventListener('input', () => {
            if (/\d/.test(inp.value) && idx < 5) inputs[idx + 1].focus();
        });
        inp.addEventListener('keydown', e => {
            if (e.key === 'Backspace' && !inp.value && idx > 0) inputs[idx - 1].focus();
        });
    });
    form.addEventListener('submit', async e => {
        e.preventDefault();
        // Clear old errors
        nonField.innerHTML = '';
        document.querySelectorAll('.error-msg').forEach(el => el.remove());

        // Build full code
        document.getElementById('fullCode').value = inputs.map(i => i.value).join('');
        const data = new FormData(form);

        try {
            const res = await fetch(form.action, {
                method: 'POST',
                headers: {'X-Requested-With': 'XMLHttpRequest'},
                body: data
            });
            if (!res.ok) throw res;
            const json = await res.json();
            // Redirect on success
            window.location = json.redirect;
        } catch (resp) {
            const {errors = {}} = await resp.json();  // structured errors :contentReference[oaicite:6]{index=6}
            // Non-field errors (__all__)
            (errors.__all__ || []).forEach(obj => {
                const p = document.createElement('p');
                p.className = 'mb-4 p-2 bg-red-100 border border-red-400 text-red-700 rounded error-msg';
                p.innerText = obj.message;
                nonField.appendChild(p);
                notyf.error(obj.message);
            });
            // Field errors
            Object.entries(errors).forEach(([field, arr]) => {
                if (field === '__all__') return;
                const inp = document.getElementById(`code1`).form.querySelector(`[name=code]`); // code is single hidden
                arr.forEach(obj => {
                    const p = document.createElement('p');
                    p.className = 'mt-1 text-sm text-red-500 error-msg';
                    p.innerText = obj.message;
                    nonField.appendChild(p);
                    notyf.error(obj.message);
                });
            });
        }
    });
});
