"""Create a demo account with synthetic data:  python seed.py   (login: demo@example.com / demo12345)"""
import sqlite3
from datetime import date, timedelta
from app import create_app

D = lambda n: (date.today() + timedelta(days=n)).isoformat()
app = create_app(); c = app.test_client()
r = c.post("/api/register", json={"email": "demo@example.com", "password": "demo12345", "name": "Asha Verma"})
if r.status_code != 201:
    raise SystemExit("Demo user already exists (delete tracker.db to reseed).")
c.put("/api/profile", json={"headline": "CS student | backend & data", "location": "Jabalpur, India",
                            "bio": "Second-year student who enjoys building small useful tools."})
for n, l, t in [("Python", 4, "language,backend"), ("SQL", 3, "database"), ("JavaScript", 3, "language,web"), ("Git", 4, "tools")]:
    c.post("/api/skills", json={"name": n, "level": l, "tags": t})
c.post("/api/projects", json={"title": "Campus Notes", "description": "Shared notes app for classmates.",
                              "tech_stack": "Flask, SQLite, JS", "github_url": "https://github.com/example/campus-notes"})
c.post("/api/certificates", json={"title": "Python Essentials", "issuer": "Example Academy", "issue_date": "2025-08-15",
                                  "credential_url": "https://example.com/cert/123"})
g = c.post("/api/goals", json={"title": "Learn SQL joins & indexing", "target_date": D(45),
                               "milestones": ["Finish tutorial", "Solve 20 practice queries", "Design a schema", "Build mini project"]}).get_json()
c.patch(f"/api/milestones/{g['milestones'][0]['id']}", json={"done": True})
c.patch(f"/api/milestones/{g['milestones'][1]['id']}", json={"done": True})
c.post("/api/goals", json={"title": "Prepare for hackathon", "target_date": D(20), "milestones": ["Form team", "Pick idea"]})
for t, o, ty, d, s in [("Backend Intern", "Acme Corp", "Internship", 12, "Applied"), ("Smart Campus Hack", "Example Univ", "Hackathon", 5, "Saved"),
                       ("Docker Workshop", "DevClub", "Workshop", 25, "Saved"), ("Data Course", "OpenLearn", "Course", 3, "Interview")]:
    o_id = c.post("/api/opportunities", json={"title": t, "organization": o, "type": ty, "deadline": D(d),
                                              "link": "https://example.com/" + t.split()[0].lower()}).get_json()["id"]
    c.patch(f"/api/opportunities/{o_id}", json={"status": s})
oid = c.post("/api/opportunities", json={"title": "Open Source Sprint", "organization": "OSS Club", "type": "Workshop", "deadline": D(1)}).get_json()["id"]
with sqlite3.connect(app.config["DB"]) as db:  # back-date one deadline so overdue handling is visible in the demo
    db.execute("UPDATE opportunities SET deadline=? WHERE id=?", (D(-4), oid))
print("Seeded. Run: python app.py  ->  http://127.0.0.1:5000  (demo@example.com / demo12345)")
