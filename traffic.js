/* ═══════════════════════════════════════════════════════
   OnTime Moving — Traffic & Analytics Engine
   1. Google Analytics 4 (replace G-XXXXXXXXXX with real ID)
   2. LocalBusiness JSON-LD structured data
   3. Social share panel
   4. Performance: preconnect hints
═══════════════════════════════════════════════════════ */
(function () {

  /* ── 1. Google Analytics 4 ─────────────────────────── */
  const GA_ID = 'G-XXXXXXXXXX'; // ← Replace with your real GA4 Measurement ID

  const gaScript = document.createElement('script');
  gaScript.async = true;
  gaScript.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
  document.head.appendChild(gaScript);

  window.dataLayer = window.dataLayer || [];
  function gtag() { dataLayer.push(arguments); }
  gtag('js', new Date());
  gtag('config', GA_ID, { anonymize_ip: true });

  // Track page views on navigation
  gtag('event', 'page_view', {
    page_title: document.title,
    page_location: window.location.href,
  });

  // Track CTA clicks
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('a[href*="booknow"], a[href*="tel:"], .nav-highlight, .hp-btn-primary, .cta-btn-white, .submit-btn');
    if (btn) {
      gtag('event', 'cta_click', {
        event_category: 'engagement',
        event_label: btn.textContent.trim().slice(0, 50),
        page: window.location.pathname,
      });
    }
  });


  /* ── 2. LocalBusiness JSON-LD ──────────────────────── */
  const schema = {
    '@context': 'https://schema.org',
    '@type': 'MovingCompany',
    name: 'OnTime Moving and Storage',
    url: 'https://jcvancity2022.github.io/OntimeMovingUPDATE/',
    logo: 'https://jcvancity2022.github.io/OntimeMovingUPDATE/images/homepage/homepageimage1.png',
    image: 'https://jcvancity2022.github.io/OntimeMovingUPDATE/images/homepage/homepageimage1.png',
    description: 'Professional moving company serving the Lower Mainland, BC since 2003. BBB A+ accredited. Free in-home estimates, transparent pricing, fully licensed and insured.',
    telephone: '+16045050026',
    email: 'info@ontime-moving.com',
    address: {
      '@type': 'PostalAddress',
      streetAddress: '104-1525 Broadway St',
      addressLocality: 'Port Coquitlam',
      addressRegion: 'BC',
      postalCode: 'V3C 6M2',
      addressCountry: 'CA',
    },
    geo: {
      '@type': 'GeoCoordinates',
      latitude: 49.2607,
      longitude: -122.7897,
    },
    openingHoursSpecification: {
      '@type': 'OpeningHoursSpecification',
      dayOfWeek: ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],
      opens: '08:00',
      closes: '20:00',
    },
    priceRange: '$$',
    aggregateRating: {
      '@type': 'AggregateRating',
      ratingValue: '4.2',
      reviewCount: '52',
      bestRating: '5',
    },
    sameAs: [
      'https://www.bbb.org/ca/bc/port-coquitlam/profile/movers/ontime-moving-storage-0037-49782',
    ],
    areaServed: [
      'Vancouver', 'Burnaby', 'Port Coquitlam', 'Coquitlam', 'Port Moody',
      'Surrey', 'Langley', 'Richmond', 'Lower Mainland',
    ],
    hasOfferCatalog: {
      '@type': 'OfferCatalog',
      name: 'Moving Services',
      itemListElement: [
        { '@type': 'Offer', itemOffered: { '@type': 'Service', name: 'Residential Moving' } },
        { '@type': 'Offer', itemOffered: { '@type': 'Service', name: 'Commercial Moving' } },
        { '@type': 'Offer', itemOffered: { '@type': 'Service', name: 'Containerized Storage' } },
        { '@type': 'Offer', itemOffered: { '@type': 'Service', name: 'Packing Services' } },
        { '@type': 'Offer', itemOffered: { '@type': 'Service', name: 'Long-Distance Moving' } },
      ],
    },
  };

  const ldScript = document.createElement('script');
  ldScript.type = 'application/ld+json';
  ldScript.textContent = JSON.stringify(schema);
  document.head.appendChild(ldScript);


  /* ── 3. Social Share Panel ─────────────────────────── */
  const shareCSS = `
    .share-fab {
      position: fixed;
      right: 20px;
      bottom: 100px;
      z-index: 999;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
    }
    .share-fab-toggle {
      width: 44px; height: 44px;
      border-radius: 50%;
      background: linear-gradient(135deg, #d32f2f, #b71c1c);
      border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      color: #fff; font-size: 1.1rem;
      box-shadow: 0 4px 16px rgba(211,47,47,0.4);
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .share-fab-toggle:hover { transform: scale(1.08); box-shadow: 0 6px 20px rgba(211,47,47,0.5); }
    .share-fab-buttons {
      display: none;
      flex-direction: column;
      gap: 8px;
      align-items: center;
    }
    .share-fab-buttons.open { display: flex; }
    .share-btn {
      width: 40px; height: 40px;
      border-radius: 50%;
      border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      font-size: 1rem; color: #fff;
      box-shadow: 0 3px 10px rgba(0,0,0,0.2);
      transition: transform 0.2s ease;
      text-decoration: none;
    }
    .share-btn:hover { transform: scale(1.1); }
    .share-btn-fb  { background: #1877f2; }
    .share-btn-x   { background: #000; }
    .share-btn-wa  { background: #25d366; }
    .share-btn-mail{ background: #5f6b82; }
    .share-btn-copy{ background: #0a0f1a; }
    .share-copied { font-size: 0.65rem; color: #0a0f1a; font-weight: 700; }
  `;
  const styleEl = document.createElement('style');
  styleEl.textContent = shareCSS;
  document.head.appendChild(styleEl);

  const pageUrl  = encodeURIComponent(window.location.href);
  const pageTitle = encodeURIComponent(document.title);

  const fab = document.createElement('div');
  fab.className = 'share-fab';
  fab.innerHTML = `
    <div class="share-fab-buttons" id="shareFabBtns">
      <a class="share-btn share-btn-fb" href="https://www.facebook.com/sharer/sharer.php?u=${pageUrl}" target="_blank" rel="noopener" title="Share on Facebook">f</a>
      <a class="share-btn share-btn-x"  href="https://twitter.com/intent/tweet?url=${pageUrl}&text=${pageTitle}" target="_blank" rel="noopener" title="Share on X">✕</a>
      <a class="share-btn share-btn-wa" href="https://wa.me/?text=${pageTitle}%20${pageUrl}" target="_blank" rel="noopener" title="Share on WhatsApp">💬</a>
      <a class="share-btn share-btn-mail" href="mailto:?subject=${pageTitle}&body=Check%20this%20out%3A%20${pageUrl}" title="Share by Email">✉</a>
      <button class="share-btn share-btn-copy" id="shareCopyFab" title="Copy link">🔗</button>
    </div>
    <button class="share-fab-toggle" id="shareFabToggle" title="Share this page">↗</button>
  `;
  document.body.appendChild(fab);

  document.getElementById('shareFabToggle').addEventListener('click', function () {
    const btns = document.getElementById('shareFabBtns');
    btns.classList.toggle('open');
    this.textContent = btns.classList.contains('open') ? '✕' : '↗';
  });

  document.getElementById('shareCopyFab').addEventListener('click', function () {
    navigator.clipboard.writeText(window.location.href).then(() => {
      this.textContent = '✓';
      setTimeout(() => { this.textContent = '🔗'; }, 2000);
    });
  });


  /* ── 4. Unofficial disclaimer banner ──────────────── */
  const disclaimerCSS = `
    .unofficial-disclaimer {
      position: fixed;
      bottom: 0; left: 0; right: 0;
      z-index: 10000;
      background: rgba(10,15,26,0.93);
      backdrop-filter: blur(12px);
      color: rgba(255,255,255,0.75);
      font-size: 0.72rem;
      text-align: center;
      padding: 7px 16px;
      letter-spacing: 0.01em;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      border-top: 1px solid rgba(255,255,255,0.08);
    }
    .unofficial-disclaimer span { flex: 1; }
    .unofficial-disclaimer button {
      background: none; border: none;
      color: rgba(255,255,255,0.45);
      font-size: 1rem; cursor: pointer;
      padding: 0 4px; line-height: 1;
      flex-shrink: 0;
    }
    .unofficial-disclaimer button:hover { color: #fff; }
  `;
  const discStyle = document.createElement('style');
  discStyle.textContent = disclaimerCSS;
  document.head.appendChild(discStyle);

  const disc = document.createElement('div');
  disc.className = 'unofficial-disclaimer';
  disc.setAttribute('role', 'note');
  disc.innerHTML = `
    <span>⚠️ This is an <strong>unofficial</strong> fan-made website. For the official OnTime Moving &amp; Storage site, call <a href="tel:+16045050026" style="color:#ef5350;">(604) 505-0026</a> or visit the BBB listing.</span>
    <button onclick="this.parentElement.style.display='none'" aria-label="Dismiss disclaimer">✕</button>
  `;
  document.body.appendChild(disc);


  /* ── 5. Performance: preconnect hints ─────────────── */
  [
    'https://fonts.googleapis.com',
    'https://fonts.gstatic.com',
    'https://www.googletagmanager.com',
  ].forEach(href => {
    if (!document.querySelector(`link[href="${href}"]`)) {
      const link = document.createElement('link');
      link.rel = 'preconnect';
      link.href = href;
      link.crossOrigin = '';
      document.head.appendChild(link);
    }
  });

})();
