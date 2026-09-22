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
      const country = document.getElementById("home-country");
      const level = document.getElementById("home-level");

      const filters = {
        country: country ? country.value : "",
        degree: level ? level.value : "",
      };

      const params = new URLSearchParams();
      if (filters.country) params.set("country", filters.country);
      if (filters.degree) params.set("degree", filters.degree);
      const qs = params.toString();
      const target = "page=programs" + (qs ? "&" + qs : "");

      // Remember the search so the dashboard can open the matching Programs
      // list after the auth detour. A cookie (not sessionStorage) so it
      // survives the server redirects and any tab; it expires in 5 minutes.
      // Searching with nothing selected is still a search: it opens the full
      // Programs listing.
      if (window.PendingSearch) window.PendingSearch.set(target);

      if (config.isLoggedIn) {
        // Already signed in: jump straight to the (filtered) Programs page.
        window.location.href = (urls.dashboard || "/dashboard/") + "?" + target;
        return;
      }

      // Guests must register or sign in first; the selection travels with them
      // and is applied once they reach the dashboard. A failing notification
      // must never block the redirect, hence the try/catch.
      try {
        // Toast comes from the single notifier configured in base.html.
        window.notify(
          t.searchInfo ||
            "Registration is required to see programs matching your search.",
          "info",
        );
      } catch (e) {}
      setTimeout(() => {
        window.location.href =
          (urls.register || "/accounts/register/") + (qs ? "?" + qs : "");
      }, 1200);
    });
  }

  /* ---------- 4. Newsletter Form (Located in the Footer) ---------- */
  function initNewsletter() {
    document.querySelectorAll("[data-newsletter]").forEach((form) => {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        window.notify(
          t.newsletterSuccess || "Thank you! You are on the list.",
          "success",
        );
        form.reset();
      });
    });
  }

  // Mobile Menu Toggle
  const menuBtn = document.getElementById("mobile-menu-btn");
  const mobileMenu = document.getElementById("mobile-menu");
  const menuIcon = document.getElementById("mobile-menu-icon");

  if (menuBtn && mobileMenu) {
    const setMenuState = (open) => {
      mobileMenu.classList.toggle("active", open);
      menuBtn.classList.toggle("active", open);
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
      if (menuIcon) {
        menuIcon.classList.toggle("fa-bars", !open);
        menuIcon.classList.toggle("fa-times", open);
      }
    };

    menuBtn.addEventListener("click", () => {
      setMenuState(!mobileMenu.classList.contains("active"));
    });

    // Close menu smoothly when a link is clicked
    mobileMenu.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => setMenuState(false));
    });

    // Close on Escape
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && mobileMenu.classList.contains("active")) {
        setMenuState(false);
        menuBtn.focus();
      }
    });

    // Reset when returning to desktop layout (CSS hides the menu there anyway)
    window.addEventListener("resize", () => {
      if (window.innerWidth >= 1024 && mobileMenu.classList.contains("active")) {
        setMenuState(false);
      }
    });

    // Dismiss on page scroll so the dropdown never sits over the content
    window.addEventListener(
      "scroll",
      () => {
        if (window.scrollY > 10 && mobileMenu.classList.contains("active")) {
          setMenuState(false);
        }
      },
      { passive: true }
    );

    // Dismiss on tap outside the menu (the button's own click is handled above)
    document.addEventListener("click", (e) => {
      if (!mobileMenu.classList.contains("active")) return;
      if (mobileMenu.contains(e.target) || menuBtn.contains(e.target)) return;
      setMenuState(false);
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
