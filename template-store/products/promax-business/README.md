# Pro Max Business Template

## Customize your content
Edit `content.json` — headlines, stats, features, pricing, testimonials and images all live there. No HTML editing required. Reload the page to see changes.

## Customize your look
Open `styles.css` and edit the `:root` block at the top (colors, fonts, spacing, radius). Or set `"theme"` in `content.json` to `default`, `emerald`, `rose`, `slate` or `sunset`.

## Run the site with lead storage
The contact form saves every submission to a local database. To enable it:

```
cd backend
pip install -r requirements.txt
copy ..\.env.example ..\.env      (or: cp ../.env.example ../.env)
python app.py
```

Then open `http://localhost:5000`. Submissions are stored in `backend/leads.db` and viewable at `http://localhost:5000/admin.html` using the `ADMIN_TOKEN` set in `.env`.

Opening `index.html` directly (without running `app.py`) still works for browsing — the contact form will just show a message asking you to start the local server.

## Deploying
Host `app.py` on any Python-friendly host (Render, Railway, PythonAnywhere, a VPS) to keep lead storage live in production, or swap the `/api/leads` endpoint for your own CRM/email integration.
