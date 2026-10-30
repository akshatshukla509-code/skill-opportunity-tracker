"""Run:  python -m unittest discover -s tests -v"""
import os, sys, sqlite3, tempfile, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app

D = lambda n: (date.today() + timedelta(days=n)).isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mkstemp(suffix=".db")[1]
        self.app = create_app(self.path)
        self.c = self.user("a@x.com", "Ann")

    def tearDown(self):
        os.remove(self.path)

    def user(self, email, name):
        c = self.app.test_client()
        r = c.post("/api/register", json={"email": email, "password": "secret123", "name": name})
        self.assertEqual(r.status_code, 201)
        return c

    def goal(self, ms=("a", "b", "c", "d")):
        return self.c.post("/api/goals", json={"title": "Learn SQL", "target_date": D(30), "milestones": list(ms)}).get_json()

    def opp(self, **kw):
        d = dict(title="Intern", organization="Acme", type="Internship", deadline=D(10)); d.update(kw)
        return self.c.post("/api/opportunities", json=d)


class AuthValidation(Base):
    def test_register_rules(self):
        c = self.app.test_client()
        self.assertEqual(c.post("/api/register", json={"email": "bad", "password": "short", "name": ""}).status_code, 422)
        self.assertEqual(c.post("/api/register", json={"email": "a@x.com", "password": "secret123", "name": "Dup"}).status_code, 409)

    def test_login_logout_and_401(self):
        c = self.app.test_client()
        self.assertEqual(c.get("/api/skills").status_code, 401)
        self.assertEqual(c.post("/api/login", json={"email": "a@x.com", "password": "wrong"}).status_code, 401)
        self.assertEqual(c.post("/api/login", json={"email": "a@x.com", "password": "secret123"}).status_code, 200)
        c.post("/api/logout"); self.assertEqual(c.get("/api/skills").status_code, 401)

    def test_skill_validation_and_duplicates(self):
        p = lambda **k: self.c.post("/api/skills", json=k)
        self.assertEqual(p(name="Python", level=4).status_code, 201)
        self.assertEqual(p(name="  python ", level=2).status_code, 409)       # case/space-insensitive duplicate
        self.assertEqual(p(name="Go", level=9).status_code, 422)
        self.assertEqual(p(name="Go", level="x").status_code, 422)
        self.assertEqual(p(level=3).status_code, 422)

    def test_url_validation_and_project_duplicates(self):
        ok = dict(title="App", github_url="https://github.com/u/app")
        self.assertEqual(self.c.post("/api/projects", json=ok).status_code, 201)
        self.assertEqual(self.c.post("/api/projects", json=ok).status_code, 409)
        self.assertEqual(self.c.post("/api/projects", json={**ok, "title": "App2"}).status_code, 201)  # same link, other title: allowed
        for bad in ("notaurl", "ftp://x.com", "javascript:alert(1)", "http://"):
            r = self.c.post("/api/projects", json={"title": "B" + bad, "github_url": bad})
            self.assertEqual(r.status_code, 422, bad); self.assertIn("github_url", r.get_json()["fields"])
        r = self.c.post("/api/projects", json={"title": "C", "github_url": "https://g.com/a", "demo_url": "bad"})
        self.assertIn("demo_url", r.get_json()["fields"])

    def test_sensitive_data_rejected(self):
        self.assertEqual(self.c.put("/api/profile", json={"bio": "my password is hunter2"}).status_code, 422)
        self.assertEqual(self.c.put("/api/profile", json={"bio": "ID 1234 5678 9012"}).status_code, 422)
        self.assertEqual(self.c.put("/api/profile", json={"bio": "Loves Python", "headline": "CS student"}).status_code, 200)

    def test_certificate_date(self):
        r = self.c.post("/api/certificates", json={"title": "AWS", "issuer": "Amazon", "issue_date": "31-12-2024"})
        self.assertEqual(r.status_code, 422)


class Goals(Base):
    def test_progress_calculation(self):
        g = self.goal(); self.assertEqual(g["progress"], 0)
        m = g["milestones"]
        self.assertEqual(self.c.patch(f"/api/milestones/{m[0]['id']}", json={"done": True}).get_json()["progress"], 25)
        self.assertEqual(self.c.patch(f"/api/milestones/{m[1]['id']}", json={"done": True}).get_json()["progress"], 50)
        for x in m[2:]: out = self.c.patch(f"/api/milestones/{x['id']}", json={"done": True}).get_json()
        self.assertEqual(out["progress"], 100)
        self.assertEqual(self.c.patch(f"/api/milestones/{m[0]['id']}", json={"done": False}).get_json()["progress"], 75)

    def test_rounding_empty_and_idempotency(self):
        g = self.goal(("a", "b", "c")); mid = g["milestones"][0]["id"]
        for _ in range(3): out = self.c.patch(f"/api/milestones/{mid}", json={"done": True}).get_json()
        self.assertEqual((out["done"], out["progress"]), (1, 33))               # repeated check counted once
        self.assertEqual(self.goal(())["progress"], 0)                          # no milestones: no ZeroDivisionError
        self.c.post(f"/api/goals/{g['id']}/milestones", json={"title": "e"})
        self.assertEqual(self.c.get(f"/api/goals/{g['id']}").get_json()["progress"], 25)

    def test_goal_validation(self):
        self.assertEqual(self.c.post("/api/goals", json={"title": "x", "target_date": "soon"}).status_code, 422)
        self.assertEqual(self.c.post("/api/goals", json={"title": "x", "target_date": D(5), "milestones": ["ok", ""]}).status_code, 422)


class Opportunities(Base):
    def test_future_deadline_required(self):
        self.assertEqual(self.opp(deadline=D(-1)).status_code, 422)
        self.assertEqual(self.opp(deadline=D(0)).status_code, 201)
        self.assertEqual(self.opp(title="X", type="Party").status_code, 422)
        self.assertEqual(self.opp(title="Y", link="nope").status_code, 422)

    def test_status_history_and_repeat_updates(self):
        o = self.opp().get_json(); self.assertEqual(o["status"], "Saved")
        for _ in range(3): r = self.c.patch(f"/api/opportunities/{o['id']}", json={"status": "Applied"})
        self.assertEqual(r.get_json()["status"], "Applied")
        self.c.patch(f"/api/opportunities/{o['id']}", json={"status": "Interview"})
        h = self.c.get(f"/api/opportunities/{o['id']}/history").get_json()
        self.assertEqual([(x["old_status"], x["new_status"]) for x in h], [(None, "Saved"), ("Saved", "Applied"), ("Applied", "Interview")])
        self.assertTrue(all(x["changed_at"] for x in h))
        self.assertEqual(self.c.patch(f"/api/opportunities/{o['id']}", json={"status": "Nope"}).status_code, 422)

    def test_overdue_flag(self):
        o = self.opp().get_json(); self.assertFalse(o["overdue"])
        with sqlite3.connect(self.path) as db: db.execute("UPDATE opportunities SET deadline=?", (D(-3),))
        self.assertTrue(self.c.get(f"/api/opportunities/{o['id']}").get_json()["overdue"])
        self.assertEqual(len(self.c.get("/api/opportunities?overdue=1").get_json()), 1)
        self.assertEqual(self.c.get("/api/dashboard").get_json()["counts"]["overdue"], 1)
        self.c.patch(f"/api/opportunities/{o['id']}", json={"status": "Completed"})   # finished work is never overdue
        self.assertFalse(self.c.get(f"/api/opportunities/{o['id']}").get_json()["overdue"])
        self.assertEqual(self.c.patch(f"/api/opportunities/{o['id']}", json={"deadline": D(-9)}).status_code, 422)

    def test_filters_and_sorting(self):
        self.opp(title="A", deadline=D(20)); self.opp(title="B", type="Hackathon", deadline=D(5))
        self.assertEqual([x["title"] for x in self.c.get("/api/opportunities?sort=deadline").get_json()], ["B", "A"])
        self.assertEqual([x["title"] for x in self.c.get("/api/opportunities?sort=-deadline").get_json()], ["A", "B"])
        self.assertEqual([x["title"] for x in self.c.get("/api/opportunities?type=Hackathon").get_json()], ["B"])


class Ownership(Base):
    def test_other_users_cannot_touch_data(self):
        b = self.user("b@x.com", "Bob")
        sid = self.c.post("/api/skills", json={"name": "Rust", "level": 3}).get_json()["id"]
        gid = self.goal()
        oid = self.opp().get_json()["id"]
        for method, url, js in [("get", f"/api/skills/{sid}", None), ("patch", f"/api/skills/{sid}", {"level": 1}),
                                ("delete", f"/api/skills/{sid}", None), ("get", f"/api/goals/{gid['id']}", None),
                                ("patch", f"/api/milestones/{gid['milestones'][0]['id']}", {"done": True}),
                                ("post", f"/api/goals/{gid['id']}/milestones", {"title": "x"}),
                                ("patch", f"/api/opportunities/{oid}", {"status": "Applied"}),
                                ("get", f"/api/opportunities/{oid}/history", None), ("delete", f"/api/opportunities/{oid}", None)]:
            self.assertEqual(getattr(b, method)(url, json=js).status_code, 404, url)
        self.assertEqual(b.get("/api/skills").get_json(), [])
        self.assertEqual(b.get("/api/dashboard").get_json()["counts"]["goals"], 0)
        self.assertEqual(self.c.get(f"/api/skills/{sid}").status_code, 200)             # still intact for the owner
        self.assertEqual(b.post("/api/skills", json={"name": "Rust", "level": 2}).status_code, 201)  # duplicates are per user


class DashboardPortfolioPersistence(Base):
    def test_empty_dashboard(self):
        d = self.c.get("/api/dashboard").get_json()
        self.assertEqual(sum(d["counts"].values()), 0); self.assertEqual(d["upcoming"], [])

    def test_dashboard_contents(self):
        self.c.post("/api/skills", json={"name": "SQL", "level": 3}); self.opp(deadline=D(7)); self.opp(title="Far", deadline=D(90))
        d = self.c.get("/api/dashboard").get_json()
        self.assertEqual((d["counts"]["skills"], d["counts"]["opportunities"], len(d["upcoming"])), (1, 2, 1))
        self.assertGreaterEqual(len(d["activity"]), 3)

    def test_portfolio_privacy_and_sharing(self):
        self.c.post("/api/skills", json={"name": "Flask", "level": 4}); self.opp(title="SecretOpp")
        t = self.c.get("/api/portfolio").get_json()["text"]
        self.assertIn("Flask", t); self.assertNotIn("a@x.com", t); self.assertNotIn("SecretOpp", t)
        self.assertTrue(self.c.get("/api/portfolio/pdf").data.startswith(b"%PDF"))
        url = self.c.post("/api/share", json={"enabled": True}).get_json()["share_url"]
        anon = self.app.test_client()
        self.assertIn("Flask", anon.get(url).get_data(as_text=True))
        self.c.post("/api/share", json={"enabled": False})
        self.assertEqual(anon.get(url).status_code, 404)

    def test_data_persists_across_restart(self):
        self.c.post("/api/skills", json={"name": "Persist", "level": 5})
        c2 = create_app(self.path).test_client()                         # "restart": new app, same DB file
        self.assertEqual(c2.post("/api/login", json={"email": "a@x.com", "password": "secret123"}).status_code, 200)
        self.assertEqual(c2.get("/api/skills").get_json()[0]["name"], "Persist")


if __name__ == "__main__":
    unittest.main()
