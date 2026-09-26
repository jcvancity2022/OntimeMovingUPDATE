// Hydrates the page from content.json (the site's single source of truth)
// and wires the contact form to the local leads API in backend/app.py.

async function loadContent() {
  let content;
  try {
    const res = await fetch('content.json');
    content = await res.json();
  } catch (err) {
    console.warn('content.json could not be loaded — showing built-in defaults.', err);
    return;
  }

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el && value != null) el.textContent = value;
  };
  const setAttr = (id, attr, value) => {
    const el = document.getElementById(id);
    if (el && value != null) el.setAttribute(attr, value);
  };

  if (content.theme) document.documentElement.setAttribute('data-theme', content.theme);

  // Brand / nav
  if (content.brand) {
    document.querySelectorAll('#brand-logo, #footer-logo').forEach((el) => {
      el.innerHTML = `${content.brand.name}<span>${content.brand.accent || ''}</span>`;
    });
  }

  // Hero
  if (content.hero) {
    const h = content.hero;
    setText('hero-badge', h.badge);
    setText('hero-title', h.title);
    setText('hero-subtitle', h.subtitle);
    setText('hero-cta-primary', h.primaryCta);
    setText('hero-cta-secondary', h.secondaryCta);
    setAttr('hero-image', 'src', h.image);
    const statsEl = document.getElementById('hero-stats');
    if (statsEl && Array.isArray(h.stats)) {
      statsEl.innerHTML = h.stats.map(s => `<div><strong>${s.value}</strong><span>${s.label}</span></div>`).join('');
    }
  }

  // Logo strip
  if (content.logoStrip) {
    setText('logo-strip-label', content.logoStrip.label);
    const itemsEl = document.getElementById('logo-strip-items');
    if (itemsEl && Array.isArray(content.logoStrip.items)) {
      itemsEl.innerHTML = content.logoStrip.items.map(i => `<span>${i}</span>`).join('');
    }
  }

  // Features
  if (content.features) {
    setText('features-label', content.features.label);
    setText('features-title', content.features.title);
    setText('features-subtitle', content.features.subtitle);
    const grid = document.getElementById('features-grid');
    if (grid && Array.isArray(content.features.items)) {
      grid.innerHTML = content.features.items.map(f => `
        <div class="feature-card">
          <div class="feature-icon">${f.icon}</div>
          <h3>${f.title}</h3>
          <p>${f.text}</p>
        </div>`).join('');
    }
  }

  // About
  if (content.about) {
    const a = content.about;
    setText('about-label', a.label);
    setText('about-title', a.title);
    setText('about-text', a.text);
    setAttr('about-image', 'src', a.image);
    setText('about-badge-value', a.badgeValue);
    setText('about-badge-label', a.badgeLabel);
    const bulletsEl = document.getElementById('about-bullets');
    if (bulletsEl && Array.isArray(a.bullets)) {
      bulletsEl.innerHTML = a.bullets.map(b => `<li>${b}</li>`).join('');
    }
  }

  // Pricing
  if (content.pricing) {
    setText('pricing-label', content.pricing.label);
    setText('pricing-title', content.pricing.title);
    setText('pricing-subtitle', content.pricing.subtitle);
    const grid = document.getElementById('pricing-grid');
    if (grid && Array.isArray(content.pricing.plans)) {
      grid.innerHTML = content.pricing.plans.map(p => `
        <div class="price-card${p.featured ? ' featured' : ''}">
          <h3>${p.name}</h3>
          <div class="price-amount">${p.price}<span>${p.period}</span></div>
          <ul class="price-list">${p.items.map(i => `<li>${i}</li>`).join('')}</ul>
          <a href="#contact" class="btn ${p.featured ? 'btn-primary' : 'btn-dark'}">Choose ${p.name}</a>
        </div>`).join('');
    }
  }

  // Testimonials
  if (content.testimonials) {
    setText('testimonials-label', content.testimonials.label);
    setText('testimonials-title', content.testimonials.title);
    setText('testimonials-subtitle', content.testimonials.subtitle);
    const grid = document.getElementById('testimonial-grid');
    if (grid && Array.isArray(content.testimonials.items)) {
      grid.innerHTML = content.testimonials.items.map(t => `
        <div class="testimonial-card">
          <div class="stars">★★★★★</div>
          <p>"${t.quote}"</p>
          <div class="testimonial-author"><div class="avatar"></div><div><strong>${t.name}</strong><span>${t.role}</span></div></div>
        </div>`).join('');
    }
  }

  // CTA + contact form copy
  if (content.cta) {
    setText('cta-title', content.cta.title);
    setText('cta-text', content.cta.text);
    setAttr('cta-email-link', 'href', `mailto:${content.cta.email}`);
  }
  if (content.contactForm) {
    setText('contact-form-title', content.contactForm.title);
    setText('contact-form-text', content.contactForm.text);
  }

  // Footer
  if (content.footer) {
    setText('footer-tagline', content.footer.tagline);
    setText('footer-copyright', content.footer.copyright);
  }

  return content;
}

function wireLeadForm(content) {
  const form = document.getElementById('lead-form');
  const status = document.getElementById('lead-form-status');
  if (!form) return;

  const messages = (content && content.contactForm) || {};

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    status.className = 'lead-form-status';
    status.textContent = 'Sending...';

    const payload = Object.fromEntries(new FormData(form).entries());

    try {
      const res = await fetch('/api/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Request failed');
      status.className = 'lead-form-status success';
      status.textContent = messages.successMessage || 'Thanks! Your message has been received.';
      form.reset();
    } catch (err) {
      status.className = 'lead-form-status error';
      status.textContent = 'Could not reach the local server. Run backend/app.py, or email us directly.';
      console.warn('Lead submit failed — is backend/app.py running?', err);
    } finally {
      submitBtn.disabled = false;
    }
  });
}

loadContent().then(wireLeadForm);
