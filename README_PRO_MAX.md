What's changed — "Pro Max" homepage upgrades

- Accessibility: added `meta description`, `theme-color`, a skip link, and ARIA toggles for mobile navigation.
- Responsiveness: mobile menu, responsive story grid, and scaled hero for small screens.
- Performance: hero image preloaded; content images set to `loading="lazy"` and `decoding="async"`.
- UX: improved mobile menu keyboard support (Escape to close) and better CTA layout on small screens.
- Dev: added a basic GitHub Actions workflow to run `pytest` on push/PRs.

Local preview

1. Start the existing server (if you use the included `start_server.bat`):

   ```powershell
   .\start_server.bat
   ```

2. Open http://localhost:5000/ (or the port your server uses).

Next suggested steps

- Generate responsive image sizes and update `srcset` for hero and story images.
- Audit Lighthouse and fix any remaining accessibility or performance items.
- Add end-to-end tests and a deployment workflow.

How to generate responsive images

1. Create a Python environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run the image variants generator (creates `-w{width}.jpg` and WebP files alongside sources):

```powershell
python tools/resize_images.py --src images/homepage --out images/homepage
```

3. Restart the server and verify images load with the new `srcset` entries.
