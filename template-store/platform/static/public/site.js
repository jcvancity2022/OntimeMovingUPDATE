// Renders a company's public marketing site from /api/public/companies/<slug>/content
// and wires the contact form to /api/public/companies/<slug>/leads. Multi-tenant:
// the slug is the only thing that changes between two businesses using this file.

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function getSlug() {
  const parts = location.pathname.split('/').filter(Boolean); // ['site', ':slug']
  return parts[1] || '';
}

function renderError(message) {
  document.getElementById('root').innerHTML = `
    <div class="site-error">
      <h2 style="font-family:'Poppins',sans-serif;">Site not found</h2>
      <p>${escapeHtml(message)}</p>
    </div>`;
}

function section(html) { return html; }

function renderSite(data) {
  document.title = `${data.name} | ${data.brand_name}`;
  document.documentElement.setAttribute('data-theme', data.theme || 'default');
  const c = data.content || {};
  const hero = c.hero || {}, logoStrip = c.logoStrip || {}, features = c.features || {};
  const about = c.about || {}, testimonials = c.testimonials || {}, cta = c.cta || {};
  const contactForm = c.contactForm || {}, footer = c.footer || {};

  document.getElementById('root').innerHTML = `
  <nav class="navbar">
    <div class="container">
      <a href="#" class="logo">${escapeHtml(data.brand_name)}<span>${escapeHtml(data.brand_accent || '')}</span></a>
      <ul class="nav-links">
        <li><a href="#services">Services</a></li>
        <li><a href="#about">About</a></li>
        <li><a href="#testimonials">Reviews</a></li>
        <li><a href="#contact">Contact</a></li>
      </ul>
      <button class="nav-toggle" aria-label="Menu">☰</button>
    </div>
  </nav>

  <header class="hero">
    <div class="container">
      <div>
        ${hero.badge ? `<span class="hero-badge">${escapeHtml(hero.badge)}</span>` : ''}
        <h1>${escapeHtml(hero.title || data.name)}</h1>
        <p>${escapeHtml(hero.subtitle || '')}</p>
        <div class="hero-actions">
          <a href="#contact" class="btn btn-primary">${escapeHtml(hero.primaryCta || 'Contact Us')}</a>
          <a href="#services" class="btn btn-outline">${escapeHtml(hero.secondaryCta || 'Learn More')}</a>
        </div>
        ${(hero.stats || []).length ? `<div class="hero-stats">${hero.stats.map(s => `<div><strong>${escapeHtml(s.value)}</strong><span>${escapeHtml(s.label)}</span></div>`).join('')}</div>` : ''}
      </div>
      <div class="hero-visual"><img src="${escapeHtml(hero.image || '')}" alt="${escapeHtml(data.name)}"></div>
    </div>
  </header>

  ${(logoStrip.items || []).length ? `
  <div class="logo-strip">
    <div class="container">
      <p>${escapeHtml(logoStrip.label || '')}</p>
      <div class="logo-strip-items">${logoStrip.items.map(i => `<span>${escapeHtml(i)}</span>`).join('')}</div>
    </div>
  </div>` : ''}

  ${(features.items || []).length ? `
  <section class="features reveal" id="services">
    <div class="container">
      <span class="section-label center" style="display:block;">${escapeHtml(features.label || '')}</span>
      <h2 class="section-title center">${escapeHtml(features.title || '')}</h2>
      <p class="section-sub center">${escapeHtml(features.subtitle || '')}</p>
      <div class="feature-grid">
        ${features.items.map(f => `<div class="feature-card"><div class="feature-icon">${escapeHtml(f.icon || '✨')}</div><h3>${escapeHtml(f.title)}</h3><p>${escapeHtml(f.text)}</p></div>`).join('')}
      </div>
    </div>
  </section>` : ''}

  <section class="about reveal" id="about">
    <div class="container">
      <div class="about-visual">
        <img src="${escapeHtml(about.image || '')}" alt="${escapeHtml(data.name)}">
        ${about.badgeValue ? `<div class="about-badge"><strong>${escapeHtml(about.badgeValue)}</strong><span>${escapeHtml(about.badgeLabel || '')}</span></div>` : ''}
      </div>
      <div>
        <span class="section-label">${escapeHtml(about.label || '')}</span>
        <h2 class="section-title">${escapeHtml(about.title || '')}</h2>
        <p style="color:var(--color-text-muted); font-size:1.02rem;">${escapeHtml(about.text || '')}</p>
        ${(about.bullets || []).length ? `<ul class="about-list">${about.bullets.map(b => `<li>${escapeHtml(b)}</li>`).join('')}</ul>` : ''}
        <a href="#contact" class="btn btn-primary">Get in Touch</a>
      </div>
    </div>
  </section>

  ${(testimonials.items || []).length ? `
  <section class="testimonials reveal" id="testimonials">
    <div class="container">
      <span class="section-label center" style="display:block;">${escapeHtml(testimonials.label || '')}</span>
      <h2 class="section-title center">${escapeHtml(testimonials.title || '')}</h2>
      <p class="section-sub center">${escapeHtml(testimonials.subtitle || '')}</p>
      <div class="testimonial-grid">
        ${testimonials.items.map(t => `
          <div class="testimonial-card">
            <div class="stars">★★★★★</div>
            <p>"${escapeHtml(t.quote)}"</p>
            <div class="testimonial-author"><div class="avatar"></div><div><strong>${escapeHtml(t.name)}</strong><span>${escapeHtml(t.role)}</span></div></div>
          </div>`).join('')}
      </div>
    </div>
  </section>` : ''}

  <section class="cta reveal" id="contact">
    <div class="container">
      <div class="cta-box">
        <h2>${escapeHtml(cta.title || 'Get in touch')}</h2>
        <p>${escapeHtml(cta.text || '')}</p>
        <div class="hero-actions">
          <a href="#contact-form" class="btn" style="background:#fff; color:var(--color-primary);">Send a Message</a>
          ${cta.email ? `<a href="mailto:${escapeHtml(cta.email)}" class="btn btn-outline">Email Us</a>` : ''}
        </div>
      </div>

      <div class="contact-form-wrap" id="contact-form">
        <h3>${escapeHtml(contactForm.title || 'Get in touch')}</h3>
        <p style="color:var(--color-text-muted);">${escapeHtml(contactForm.text || '')}</p>
        <form id="lead-form" class="lead-form">
          <div class="lead-form-row">
            <input type="text" name="name" placeholder="Your name" required>
            <input type="email" name="email" placeholder="Email address" required>
          </div>
          <input type="tel" name="phone" placeholder="Phone (optional)">
          <textarea name="message" rows="4" placeholder="How can we help?" required></textarea>
          <button type="submit" class="btn btn-primary">Send Message</button>
          <p id="lead-form-status" class="lead-form-status" role="status"></p>
        </form>
      </div>
    </div>
  </section>

  <footer>
    <div class="container">
      <div class="footer-inner">
        <div class="footer-logo">${escapeHtml(data.brand_name)}<span>${escapeHtml(data.brand_accent || '')}</span></div>
        <span>${escapeHtml(footer.tagline || '')}</span>
      </div>
      <div class="footer-bottom">${escapeHtml(footer.copyright || '')}</div>
    </div>
  </footer>`;

  wireNav();
  wireReveal();
  wireContactForm(getSlug(), contactForm);
}

function wireNav() {
  document.querySelector('.nav-toggle')?.addEventListener('click', () => {
    const links = document.querySelector('.nav-links');
    links.style.display = links.style.display === 'flex' ? 'none' : 'flex';
  });
}

function wireReveal() {
  const targets = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) { targets.forEach(t => t.classList.add('in')); return; }
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('in'); io.unobserve(entry.target); } });
  }, { threshold: 0.12 });
  targets.forEach(t => io.observe(t));
}

function wireContactForm(slug, contactForm) {
  const form = document.getElementById('lead-form');
  const status = document.getElementById('lead-form-status');
  if (!form) return;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    status.className = 'lead-form-status';
    status.textContent = 'Sending...';
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      const res = await fetch(`/api/public/companies/${slug}/leads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('failed');
      status.className = 'lead-form-status success';
      status.textContent = contactForm.successMessage || 'Thanks! Your message has been received.';
      form.reset();
    } catch (err) {
      status.className = 'lead-form-status error';
      status.textContent = contactForm.errorMessage || 'Something went wrong. Please try again.';
    } finally {
      btn.disabled = false;
    }
  });
}

(async function init() {
  const slug = getSlug();
  if (!slug) return renderError('No site specified.');
  try {
    const res = await fetch(`/api/public/companies/${slug}/content`);
    if (!res.ok) throw new Error('not found');
    const data = await res.json();
    renderSite(data);
  } catch (err) {
    renderError('This site is not available. Double-check the link, or contact the business directly.');
  }
})();
