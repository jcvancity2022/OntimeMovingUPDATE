/* ═══════════════════════════════════════════════════════════════
   OnTime Moving — Motion & Micro-Interaction Engine
   Auto-applies to every page. No HTML class changes needed.
═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // Respect reduced-motion preference
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── 1. Scroll progress bar ──────────────────────────────────── */
  const bar = document.createElement('div');
  bar.id = 'scroll-progress';
  document.body.prepend(bar);

  window.addEventListener('scroll', () => {
    const pct = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100;
    bar.style.width = Math.min(pct, 100) + '%';
  }, { passive: true });


  /* ── 2. Scroll reveal via IntersectionObserver ───────────────── */
  if (!reduced) {
    // Elements to reveal on scroll — auto-targeted by selector
    const REVEAL_SELECTORS = [
      // Section headings
      'h2.section-title, h2.how-it-works-title, h2.svc-process-title, h2.svc-section-header h2',
      '.svc-section-header h2',
      '.how-it-works-title, .how-it-works-sub',
      '.section-label, .reviews-section-label',
      // Cards & grids
      '.svc-card, .value-card, .step, .svc-step, .review-card',
      '.ctc-contact-card, .ctc-hours-card',
      // Trust bars
      '.svc-trust-item, .book-trust-item, .ctc-trust-item',
      // Story rows
      '.story-row',
      // Form shells
      '.book-shell, .ctc-form-shell',
      // CTA sections
      '.cta-section h2, .svc-cta h2, .ctc-cta h2, .reviews-page-cta h2',
    ];

    const STAGGER_GRIDS = [
      '.svc-grid',
      '.values-grid',
      '.steps',
      '.svc-process-grid',
      '.reviews-grid',
      '.abt-stats',
    ];

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(el => {
        if (el.isIntersecting) {
          el.target.classList.add('revealed');
          observer.unobserve(el.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    // Apply reveal to individual elements
    REVEAL_SELECTORS.forEach(sel => {
      document.querySelectorAll(sel).forEach(el => {
        if (!el.closest('.abt-hero, .svc-hero, .book-hero, .ctc-hero, .reviews-page-hero')) {
          el.classList.add('reveal');
          observer.observe(el);
        }
      });
    });

    // Apply stagger to grid children
    STAGGER_GRIDS.forEach(sel => {
      document.querySelectorAll(sel).forEach(grid => {
        Array.from(grid.children).forEach(child => {
          child.classList.add('reveal', 'stagger-child');
          observer.observe(child);
        });
      });
    });

    // Story rows — alternating direction
    document.querySelectorAll('.story-row').forEach((row, i) => {
      row.classList.remove('reveal');
      row.classList.add(i % 2 === 0 ? 'reveal-left' : 'reveal-right');
      observer.observe(row);
    });
  }


  /* ── 3. Stat counter animation ───────────────────────────────── */
  const STAT_SELECTORS = [
    '.abt-stat-num',
    '.reviews-page-stat .stat-number',
    '.hp-stat-num',
  ];

  function animateCount(el) {
    const raw   = el.textContent.trim();
    const num   = parseFloat(raw.replace(/[^0-9.]/g, ''));
    const suffix = raw.replace(/[0-9.]/g, '');
    if (isNaN(num) || reduced) return;

    const duration = 1400;
    const start    = performance.now();
    const isFloat  = raw.includes('.');

    function step(now) {
      const p    = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      const val  = isFloat ? (num * ease).toFixed(1) : Math.round(num * ease);
      el.textContent = val + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  const countObserver = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        animateCount(e.target);
        countObserver.unobserve(e.target);
      }
    });
  }, { threshold: 0.5 });

  STAT_SELECTORS.forEach(sel => {
    document.querySelectorAll(sel).forEach(el => countObserver.observe(el));
  });


  /* ── 4. Ripple effect on primary buttons ─────────────────────── */
  if (!reduced) {
    const RIPPLE_SELECTORS = '.btn-primary, .submit-btn, .nav-highlight, .cta-btn-white, .svc-cta-white, .hp-btn-primary, .book-now-btn';

    document.querySelectorAll(RIPPLE_SELECTORS).forEach(btn => {
      btn.addEventListener('click', function (e) {
        const rect  = btn.getBoundingClientRect();
        const ripple = document.createElement('span');
        ripple.className = 'ripple-effect';
        ripple.style.left = (e.clientX - rect.left) + 'px';
        ripple.style.top  = (e.clientY - rect.top)  + 'px';
        btn.appendChild(ripple);
        ripple.addEventListener('animationend', () => ripple.remove());
      });
    });
  }


  /* ── 5. Trust-check icon pop on scroll-in ────────────────────── */
  if (!reduced) {
    const checkObserver = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.querySelectorAll(
            '.book-trust-check, .svc-trust-check, .ctc-trust-check'
          ).forEach((icon, i) => {
            setTimeout(() => icon.classList.add('trust-check-pop'), i * 80);
          });
          checkObserver.unobserve(e.target);
        }
      });
    }, { threshold: 0.4 });

    document.querySelectorAll(
      '.book-trust-inner, .svc-trust-inner, .ctc-trust-inner'
    ).forEach(el => checkObserver.observe(el));
  }


  /* ── 6. Eyebrow badge entrance ───────────────────────────────── */
  if (!reduced) {
    document.querySelectorAll(
      '.abt-eyebrow, .svc-eyebrow, .book-hero-eyebrow, .ctc-eyebrow, .reviews-hero-badge'
    ).forEach(el => el.classList.add('motion-badge-in'));
  }


  /* ── 7. Smooth magnetic feel on CTA buttons (subtle) ─────────── */
  if (!reduced) {
    document.querySelectorAll('.btn-primary, .cta-btn-white, .svc-cta-white').forEach(btn => {
      btn.addEventListener('mousemove', function (e) {
        const rect = btn.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width  - 0.5) * 6;
        const y = ((e.clientY - rect.top)  / rect.height - 0.5) * 4;
        btn.style.transform = `translateY(-2px) translate(${x}px, ${y}px)`;
      });
      btn.addEventListener('mouseleave', function () {
        btn.style.transform = '';
      });
    });
  }

})();
