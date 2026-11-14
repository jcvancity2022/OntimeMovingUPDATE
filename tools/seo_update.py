"""One-off SEO pass for the OnTime Moving site. Run from the site folder."""
import json, re

BASE = 'https://jcvancity2022.github.io/OntimeMovingUPDATE/'
BIZ_ID = BASE + '#business'

BUSINESS = {
    "@context": "https://schema.org",
    "@type": "MovingCompany",
    "@id": BIZ_ID,
    "name": "OnTime Moving and Storage",
    "url": BASE,
    "logo": BASE + "images/homepage/ontimemovingtrucks.webp",
    "image": [BASE + "images/homepage/ontimemovingtrucks.webp",
              BASE + "images/homepage/onTimeWarehouse.webp"],
    "telephone": "+1-604-505-0026",
    "email": "info@ontime-moving.com",
    "foundingDate": "2003",
    "priceRange": "$$",
    "address": {"@type": "PostalAddress", "streetAddress": "104-1525 Broadway St",
                "addressLocality": "Port Coquitlam", "addressRegion": "BC",
                "postalCode": "V3C 6M2", "addressCountry": "CA"},
    "openingHoursSpecification": [{"@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "opens": "08:00", "closes": "20:00"}],
    "areaServed": [{"@type": "City", "name": c} for c in
        ["Port Coquitlam", "Coquitlam", "Port Moody", "Vancouver", "Burnaby", "New Westminster",
         "Surrey", "Langley", "Richmond", "Maple Ridge"]] +
        [{"@type": "AdministrativeArea", "name": "Lower Mainland, British Columbia"}],
    "hasOfferCatalog": {"@type": "OfferCatalog", "name": "Moving and storage services",
        "itemListElement": [{"@type": "Offer", "itemOffered": {"@type": "Service", "name": n}} for n in
            ["Residential moving", "Commercial moving", "Packing services",
             "Containerized storage", "Long-distance moving"]]},
    "potentialAction": {"@type": "ReserveAction",
        "target": {"@type": "EntryPoint", "urlTemplate": BASE + "booknow.html"},
        "result": {"@type": "Reservation", "name": "Free moving estimate"}},
}

WEBSITE = {"@context": "https://schema.org", "@type": "WebSite", "@id": BASE + "#website",
           "url": BASE, "name": "OnTime Moving and Storage", "publisher": {"@id": BIZ_ID},
           "inLanguage": "en-CA"}


def crumbs(name, path):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": name, "item": BASE + path}]}


def page(kind, name, path, desc):
    return {"@context": "https://schema.org", "@type": kind, "@id": BASE + path + "#webpage",
            "url": BASE + path, "name": name, "description": desc,
            "isPartOf": {"@id": BASE + "#website"}, "about": {"@id": BIZ_ID}}


def ld(obj):
    return ('    <script type="application/ld+json">\n'
            + '\n'.join('    ' + l for l in json.dumps(obj, indent=2, ensure_ascii=False).splitlines())
            + '\n    </script>\n')


META = {  # file: (title, description)
    'index.html': ('Port Coquitlam Movers | Local Moving in Metro Vancouver',
                   'Local movers in Port Coquitlam serving Metro Vancouver and the Lower Mainland. Residential, commercial, packing and storage. BBB A+. Free estimates.'),
    'services.html': ('Moving Services in Port Coquitlam & Metro Vancouver',
                      'Residential, commercial and long-distance moving, packing, and containerized storage from Port Coquitlam movers serving the Lower Mainland. Free estimates.'),
    'booknow.html': ('Free Moving Estimate — Port Coquitlam & Metro Vancouver',
                     'Book a free moving estimate with Port Coquitlam movers. Pick your date and crew arrival window online — written price, no commitment, reply within 24 hours.'),
}

EXTRA_LD = {
    'index.html': [BUSINESS, WEBSITE],
    'about.html': [page('AboutPage', 'About OnTime Moving and Storage', 'about.html',
                        'Family-owned Port Coquitlam moving company, BBB A+ accredited, serving the Lower Mainland since 2003.'),
                   crumbs('About', 'about.html'), BUSINESS],
    'contact.html': [page('ContactPage', 'Contact OnTime Moving', 'contact.html',
                          'Phone, email, address and hours for OnTime Moving and Storage in Port Coquitlam, BC.'),
                     crumbs('Contact', 'contact.html'), BUSINESS],
    'reviews.html': [page('WebPage', 'OnTime Moving reviews', 'reviews.html',
                          'Customer reviews of OnTime Moving and Storage, Lower Mainland BC.'),
                     crumbs('Reviews', 'reviews.html')],
    'booknow.html': [page('WebPage', 'Book a free moving estimate', 'booknow.html',
                          'Request a free moving estimate and choose a crew arrival window.'),
                     crumbs('Book Now', 'booknow.html')],
}

NOINDEX = ['login.html', 'admin.html', 'index_old.html', 'admin_old.html', 'login_old.html',
           'login_modern.html', 'index_modern.html', 'landing-hero.html', '_draft_city_sections.html']

PRECONNECT = ('    <link rel="preconnect" href="https://fonts.googleapis.com">\n'
              '    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n')

ABOUT_IMGS = {
    'images/aboutpage/teamphoto.webp': (1092, 838),
    'images/aboutpage/movingontimeimage.webp': (1088, 694),
    'images/homepage/onTimeWarehouseinside.webp': (897, 673),
}


def load(f):
    raw = open(f, 'rb').read()
    bom = raw.startswith(b'\xef\xbb\xbf')
    s = raw.decode('utf-8-sig')
    nl = '\r\n' if '\r\n' in s else '\n'
    return s.replace('\r\n', '\n'), bom, nl


def save(f, s, bom, nl):
    open(f, 'w', encoding='utf-8-sig' if bom else 'utf-8', newline='').write(s.replace('\n', nl))


def esc(t):
    return t.replace('&', '&amp;').replace('"', '&quot;')


for f in set(META) | set(EXTRA_LD) | set(NOINDEX):
    s, bom, nl = load(f)
    changes = []

    if f in META:
        title, desc = META[f]
        assert len(title) <= 60 and len(desc) <= 160, (f, len(title), len(desc))
        s, n = re.subn(r'<title>.*?</title>', f'<title>{esc(title)}</title>', s, count=1, flags=re.S)
        s, m = re.subn(r'<meta name="description" content="[^"]*">',
                       f'<meta name="description" content="{esc(desc)}">', s, count=1)
        assert n == m == 1, f
        changes.append('title/description')

    marker = '#business"' if f == 'index.html' else '#webpage"'
    if f in EXTRA_LD and marker not in s:
        block = ''.join(ld(o) for o in EXTRA_LD[f])
        s = s.replace('</head>', block + '</head>', 1)
        changes.append('structured data')

    if f in NOINDEX and 'noindex' not in s:
        s = re.sub(r'(<meta charset="[^"]*">)', r'\1\n    <meta name="robots" content="noindex, nofollow">', s, count=1)
        changes.append('noindex')

    if 'fonts.googleapis.com/css' in s and 'rel="preconnect"' not in s:
        s = s.replace('    <link href="https://fonts.googleapis.com/css', PRECONNECT + '    <link href="https://fonts.googleapis.com/css', 1)
        changes.append('font preconnect')

    if f == 'about.html':
        for src, (w, h) in ABOUT_IMGS.items():
            pat = f'<img src="{src}"'
            if pat in s and f'{pat} width=' not in s:
                s = s.replace(pat, f'{pat} width="{w}" height="{h}" loading="lazy" decoding="async"', 1)
        changes.append('image dimensions + lazy loading')

    save(f, s, bom, nl)
    print(f'{f}: {", ".join(changes) or "no change"}')

# sitemap lastmod
s, bom, nl = load('sitemap.xml')
s = re.sub(r'<lastmod>[^<]*</lastmod>', '<lastmod>2026-11-14</lastmod>', s)
save('sitemap.xml', s, bom, nl)
print('sitemap.xml: lastmod updated')
