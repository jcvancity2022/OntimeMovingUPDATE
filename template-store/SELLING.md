# Selling the Pro Max Business Template

Two ways to sell, not mutually exclusive — most sellers start with #1 and add #2 once they have some reviews/proof.

1. **Your own storefront** (`storefront/index.html`) — you keep ~95%+ of revenue, but you supply all the traffic.
2. **A marketplace** (Etsy, Creative Market) — they supply search traffic, take a cut, and you get discovered by people not already looking for you.

I can't create accounts or enter payment details on your behalf — that's something only you can do. Everything below is written so you do the 10 minutes of account setup, then hand me the resulting links/files and I wire them in.

---

## 1. Your own storefront checkout (Gumroad — simplest)

**Why Gumroad first:** free to start, no monthly fee, handles file delivery + licensing + tax automatically, checkout link ready in minutes. Lemon Squeezy is the other common choice (better for EU VAT handling) — same steps below apply, just swap which site you sign up on.

**Steps (you do these):**
1. Go to gumroad.com → Sign Up → verify your email.
2. Click **New Product** → choose **Digital Product**.
3. Zip the product folder and upload it: `template-store/products/promax-business/` (everything inside — `index.html`, `styles.css`, `content.json`, `backend/`, `README.md`). Do this once per tier (Personal/Business/Agency), or upload once and use Gumroad's built-in "tiers"/versions feature so it's a single product with 3 price options.
4. Set the price to match the storefront: **$39** (Personal), **$79** (Business), **$249** (Agency Bundle) — or adjust however you like, just keep the storefront's copy in sync if you change them.
5. Write a short product description (see `MARKETPLACE_LISTING.md` for ready-to-paste copy — the "short description" section works well here).
6. Publish. Gumroad gives you a URL like `https://yourname.gumroad.com/l/promax-business`.
7. Repeat for each tier, or set up Gumroad's tiered pricing on one listing.

**Send me the resulting URL(s)** and I'll paste them into the `CHECKOUT_LINKS` block at the bottom of `storefront/index.html` — that's the only place they need to go; the Buy buttons pick them up automatically. Right now those buttons safely default to scrolling to the pricing section, so nothing is broken while you're mid-setup.

---

## 2. Marketplace listings (Etsy / Creative Market)

See `MARKETPLACE_LISTING.md` for the full ready-to-paste title, description, tags, and pricing for both platforms, plus a shot list of exactly which screenshots to take.

Quick version of the account-setup steps (again, you do these — I can't create the listing for you since it requires your own seller account and uploading files through their interface):
1. Create a seller account on Etsy (etsy.com/sell) or Creative Market (creativemarket.com/sell).
2. Take the screenshots listed in `MARKETPLACE_LISTING.md` (I can help you capture these via the browser if you want — just ask).
3. Zip the product folder (same one as above).
4. Paste in the title/description/tags from `MARKETPLACE_LISTING.md`.
5. Set pricing (marketplace fees differ — see the pricing note in that file).
6. Publish.

---

## Where things stand right now

- Storefront (`storefront/index.html`): live, Buy buttons wired to accept real checkout URLs the moment you have them (see `CHECKOUT_LINKS` near the closing `</body>` tag).
- Product (`template-store/products/promax-business/`): complete, tested, includes the lead-capture backend and README for buyers.
- Nothing is actually for sale yet — that only happens once you've created a real Gumroad/Lemon Squeezy/Etsy listing and I've wired in the resulting link(s).
