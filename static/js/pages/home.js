// /static/js/pages/home.js
(function () {
  "use strict";

  const config = window.AppConfig || {};
  const urls = config.urls || {};
  const t = config.translations || {};

  /* ---------- 1. Scroll Animations (Intersection Observer) ---------- */
  function initScrollAnimations() {
    const elements = document.querySelectorAll(".fade-in-up");
    if (!elements.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -50px 0px" },
    );

    elements.forEach((el) => observer.observe(el));
  }

  /* ---------- 2. Animated Stat Counters (If you kept the stats section) ---------- */
  function initCounters() {
    const numbers = document.querySelectorAll(".home-stat-number");
    if (!numbers.length) return;

    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

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
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(target * eased) + suffix;
        if (progress < 1) requestAnimationFrame(tick);
      };

      requestAnimationFrame(tick);
    };

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            run(entry.target);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.5 },
    );

    numbers.forEach((el) => observer.observe(el));
  }

  /* ---------- 3. Hero Search Button ---------- */
  function initSearch() {
    const btn = document.getElementById("home-search-btn");
    if (!btn) return;

    btn.addEventListener("click", () => {
      if (typeof Notyf !== "undefined") {
        const notyf = new Notyf({
          duration: 4000,
          position: { x: "right", y: "top" },
        });
        notyf.open({
          type: "info",
          message: t.searchInfo || "Create your free account to see programs.",
        });
      }
      setTimeout(() => {
        window.location.href = urls.register || "/accounts/register/";
      }, 1200);
    });
  }

  /* ---------- 4. Newsletter Form (Located in the Footer) ---------- */
  function initNewsletter() {
    document.querySelectorAll("[data-newsletter]").forEach((form) => {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        if (typeof Notyf !== "undefined") {
          const notyf = new Notyf({
            duration: 4000,
            position: { x: "right", y: "top" },
          });
          notyf.success(
            t.newsletterSuccess || "Thank you! You are on the list.",
          );
        }
        form.reset();
      });
    });
  }

  // Mobile Menu Toggle
  const menuBtn = document.getElementById("mobile-menu-btn");
  const mobileMenu = document.getElementById("mobile-menu");

  if (menuBtn && mobileMenu) {
    menuBtn.addEventListener("click", () => {
      const isActive = mobileMenu.classList.toggle("active");
      menuBtn.classList.toggle("active");
      menuBtn.setAttribute("aria-expanded", isActive);
    });

    // Close menu smoothly when a link is clicked
    mobileMenu.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        mobileMenu.classList.remove("active");
        menuBtn.classList.remove("active");
        menuBtn.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ---------- Initialize Everything on Page Load ---------- */
  window.ApplyBaMa.ready(() => {
    initScrollAnimations();
    initCounters();
    initSearch();
    initNewsletter();
  });
})();
