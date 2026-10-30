# Student Skill & Opportunity Tracker

One place for a student to keep skills, projects, certificates, learning goals and opportunities (internships, hackathons, workshops, courses), see progress and deadlines on a dashboard, and export or share a privacy-safe portfolio.

**Stack:** Python 3.10+, Flask (REST API), SQLite (relational DB), vanilla HTML/CSS/JS single-page UI, reportlab (PDF export), `unittest` (tests).

## Features
- Register / login (hashed passwords, session cookie); profile with validation
- Skills (level 1-5, tags, search), projects, certificates: full add / edit / delete
- Learning goals with milestone checkboxes and calculated progress bars
- Opportunities with type, deadline, link and status (Saved / Applied / Interview / Completed / Rejected), filters, sorting, overdue flag and a timestamped status history
- Dashboard: counts, upcoming deadlines, overdue items, goal progress, recent activity
- Portfolio preview, copy as text, PDF download, optional revocable public share link
- Loading, error (with retry) and empty/onboarding states; responsive and dark-mode aware layout

## Setup and run
```bash
pip install -r requirements.txt
python seed.py          # optional demo data: demo@example.com / demo12345
python app.py           # open http://127.0.0.1:5000
```
Optional environment variables: `PORT`, `TRACKER_DB` (database path), `SECRET_KEY`, `FLASK_DEBUG=1`.
The database file `tracker.db` is created automatically; data persists between restarts.

## Tests
```bash
python -m unittest discover -s tests -v     # 18 tests, ~4 s, uses temporary databases
```

## Documentation
- `docs/SETUP_FOR_BEGINNERS.md`: step-by-step setup, GitHub and hosting guide for beginners
- `docs/GUIDE.md`: architecture, ER diagram, API reference with examples, line-by-line code explanation, UI and testing notes
- `docs/Project_Guide.pdf`: the same guide as a PDF (`python docs/build_pdf.py` regenerates it)
- `schema.sql`: database schema; `seed.py`: synthetic sample data

## Business rules implemented
Ownership on every query (other users get 404) | URL validation (http/https only) | duplicate skill (name) and project (title+GitHub link) prevention per user, case-insensitive, enforced by unique indexes too | new opportunity deadline must be today or later | overdue = past deadline and still Saved/Applied/Interview | status changes write timestamped history, repeating the same status is a no-op | passwords and ID-number-like text rejected in profile fields | shared portfolio never includes email, opportunities or activity.

## Known limitations
- Single-server SQLite; no multi-device sync beyond sharing the same server
- No email verification or password reset; no CSRF token (relies on SameSite=Lax cookie and JSON-only API)
- Login attempts are not rate limited; use HTTPS and a real `SECRET_KEY` for any deployment
- "Overdue" uses the server's date; PDF uses a basic text layout
- Sample data only. Never commit `tracker.db` or `.secret_key` (already git-ignored)

## Contribution statement
Replace this paragraph with your own: what you designed, built and tested, and which AI tools you used for what.
