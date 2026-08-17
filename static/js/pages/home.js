// /static/js/pages/home.js
(function () {
    "use strict";

    const config = window.AppConfig || {};
    const urls = config.urls || {};
    const t = config.translations || {};

    /* ---------- Animated stat counters ---------- */
    function initCounters() {
        const numbers = document.querySelectorAll(".home-stat-number");
        if (!numbers.length) return;

        const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        const run = (el) => {
            const target = parseInt(el.getAttribute("data-count"), 10) || 0;
            const suffix = el.getAttribute("data-suffix") || "";

            if (reduceMotion) {
                el.textContent = target + suffix;
                return;
            }

            const duration = 1400;
            const start = performance.now();

            const tick = (now) => {
                const progress = Math.min((now - start) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
                el.textContent = Math.round(target * eased) + suffix;
                if (progress < 1) requestAnimationFrame(tick);
            };

            requestAnimationFrame(tick);
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    run(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        numbers.forEach((el) => observer.observe(el));
    }

    /* ---------- Hero search → guide to registration ---------- */
    function initSearch() {
        const btn = document.getElementById("home-search-btn");
        if (!btn) return;

        btn.addEventListener("click", () => {
            const notyf = new Notyf({ duration: 4000, position: { x: "right", y: "top" } });
            notyf.open({ type: "info", message: t.searchInfo || "Create your free account to see programs." });

            setTimeout(() => {
                window.location.href = urls.register || "/accounts/register/";
            }, 1200);
        });
    }

    /* ---------- Newsletter (decorative for now) ---------- */
    function initNewsletter() {
        document.querySelectorAll("[data-newsletter]").forEach((form) => {
            form.addEventListener("submit", (e) => {
                e.preventDefault();
                const notyf = new Notyf({ duration: 4000, position: { x: "right", y: "top" } });
                notyf.success(t.newsletterSuccess || "Thank you!");
                form.reset();
            });
        });
    }

    window.ApplyBaMa.ready(() => {
        initCounters();
        initSearch();
        initNewsletter();
    });

})();