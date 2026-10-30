"""Student Skill & Opportunity Tracker - Flask + SQLite REST API (see docs/GUIDE.md)."""
import io, os, re, secrets, sqlite3
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from flask import Flask, Response, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
OPP_TYPES = ("Internship", "Hackathon", "Workshop", "Course")
OPP_STATUS = ("Saved", "Applied", "Interview", "Completed", "Rejected")
OPEN_STATUS = ("Saved", "Applied", "Interview")  # only these can be "overdue"
# Privacy rule: profile text must not contain passwords or government-ID-like numbers.
SENSITIVE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b|password|passwd|\bssn\b|aadhaar|passport", re.I)


class ApiError(Exception):
    def __init__(self, msg, code=400, fields=None):
        self.msg, self.code, self.fields = msg, code, fields or {}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def valid_url(v):
    p = urlparse(v)
    return p.scheme in ("http", "https") and bool(p.netloc) and " " not in v


def clean(spec, data, partial=False):
    """Validate/normalise `data` against spec {field: (kind, required, max_len)}.
    kind: str | text | url | date | level | tuple-of-allowed-values."""
    out, errs = {}, {}
    for f, (kind, req, mx) in spec.items():
        if f not in data:
            if req and not partial:
                errs[f] = "This field is required"
            continue
        val = "" if data[f] is None else str(data[f]).strip()
        if not val:
            if req:
                errs[f] = "This field is required"
            else:
                out[f] = None if kind == "date" else ""
            continue
        if kind in ("str", "text", "url") and len(val) > mx:
            errs[f] = f"Maximum {mx} characters"; continue
        if kind in ("str", "text") and SENSITIVE.search(val):
            errs[f] = "Passwords and government IDs must not be stored here"; continue
        if kind == "url" and not valid_url(val):
            errs[f] = "Enter a valid link starting with http:// or https://"; continue
        if kind == "level":
            if not re.fullmatch(r"[1-5]", val):
                errs[f] = "Must be a whole number from 1 to 5"; continue
            val = int(val)
        if kind == "date":
            try:
                date.fromisoformat(val)
            except ValueError:
                errs[f] = "Use the format YYYY-MM-DD"; continue
        if isinstance(kind, tuple) and val not in kind:
            errs[f] = "Must be one of: " + ", ".join(kind); continue
        out[f] = val
    if errs:
        raise ApiError("Validation failed", 422, errs)
    return out


# ---- resource configuration for the three "simple" CRUD resources -------------------
RES = {
    "skills": dict(kind="skill", label="name", order="name COLLATE NOCASE", search=["name", "tags"], dup=["name"],
                   spec={"name": ("str", True, 60), "level": ("level", True, 0), "tags": ("str", False, 100)}),
    "projects": dict(kind="project", label="title", order="id DESC", search=["title", "tech_stack", "description"],
                     dup=["title", "github_url"],
                     spec={"title": ("str", True, 100), "description": ("text", False, 1000),
                           "tech_stack": ("str", False, 150), "github_url": ("url", True, 300),
                           "demo_url": ("url", False, 300)}),
    "certificates": dict(kind="certificate", label="title", order="issue_date DESC", search=["title", "issuer"],
                         dup=["title", "issuer"],
                         spec={"title": ("str", True, 100), "issuer": ("str", True, 100),
                               "issue_date": ("date", True, 0), "credential_url": ("url", False, 300)}),
}
PROFILE_SPEC = {"name": ("str", True, 80), "headline": ("str", False, 120), "bio": ("text", False, 500),
                "location": ("str", False, 80), "website": ("url", False, 300)}
GOAL_SPEC = {"title": ("str", True, 100), "target_date": ("date", True, 0)}
OPP_SPEC = {"title": ("str", True, 100), "organization": ("str", True, 100), "type": (OPP_TYPES, True, 0),
            "deadline": ("date", True, 0), "link": ("url", False, 300), "status": (OPP_STATUS, False, 0)}


def create_app(db_path=None):
    app = Flask(__name__, static_folder=os.path.join(BASE, "static"))
    app.config["DB"] = db_path or os.environ.get("TRACKER_DB", os.path.join(BASE, "tracker.db"))
    key_file = os.path.join(BASE, ".secret_key")
    if os.environ.get("SECRET_KEY"):
        app.secret_key = os.environ["SECRET_KEY"]
    elif db_path:  # tests: throw-away key
        app.secret_key = secrets.token_hex(16)
    else:  # stable key so logins survive restarts; never committed (.gitignore)
        if not os.path.exists(key_file):
            open(key_file, "w").write(secrets.token_hex(32))
        app.secret_key = open(key_file).read()
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1")  # set on HTTPS hosting
    with sqlite3.connect(app.config["DB"]) as c:
        c.executescript(open(os.path.join(BASE, "schema.sql")).read())

    # ---- helpers -----------------------------------------------------------------
    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_):
        if (c := g.pop("db", None)) is not None:
            c.close()

    uid = lambda: session["uid"]
    body = lambda: request.get_json(silent=True) or {}

    def log(text):
        db().execute("INSERT INTO activity(user_id,text,at) VALUES(?,?,?)", (uid(), text, now()))

    def owned(table, rid):
        """Fetch a row only if it belongs to the logged-in user, else 404 (never reveals other users' ids)."""
        r = db().execute(f"SELECT * FROM {table} WHERE id=? AND user_id=?", (rid, uid())).fetchone()
        if not r:
            raise ApiError("Not found", 404)
        return r

    def check_dup(table, cols, vals, exclude=None):
        sql = f"SELECT id FROM {table} WHERE user_id=? AND " + " AND ".join(f"lower({c})=lower(?)" for c in cols)
        args = [uid()] + [vals[c] for c in cols]
        if exclude:
            sql += " AND id!=?"; args.append(exclude)
        if db().execute(sql, args).fetchone():
            raise ApiError("Duplicate: " + " + ".join(cols) + " already exists", 409)

    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(error=e.msg, fields=e.fields), e.code

    @app.errorhandler(404)
    def nf(_):
        return jsonify(error="Not found"), 404

    @app.errorhandler(Exception)
    def boom(e):
        app.logger.exception(e)
        return jsonify(error="Server error"), 500

    @app.before_request
    def require_login():
        if request.path.startswith("/api/") and request.path not in ("/api/register", "/api/login") \
                and "uid" not in session:
            raise ApiError("Login required", 401)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    # ---- auth + profile ----------------------------------------------------------
    @app.post("/api/register")
    def register():
        d = body(); email = str(d.get("email", "")).strip().lower(); pw = str(d.get("password", ""))
        errs = {}
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): errs["email"] = "Enter a valid email"
        if len(pw) < 8: errs["password"] = "At least 8 characters"
        prof = {}
        try: prof = clean({"name": PROFILE_SPEC["name"]}, d)
        except ApiError as e: errs.update(e.fields)
        if errs: raise ApiError("Validation failed", 422, errs)
        if db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise ApiError("Email already registered", 409, {"email": "Already registered"})
        cur = db().execute("INSERT INTO users(email,pw_hash,created_at) VALUES(?,?,?)",
                           (email, generate_password_hash(pw), now()))
        db().execute("INSERT INTO profiles(user_id,name) VALUES(?,?)", (cur.lastrowid, prof["name"]))
        db().commit()
        session["uid"] = cur.lastrowid
        return jsonify(id=cur.lastrowid, email=email, name=prof["name"]), 201

    @app.post("/api/login")
    def login():
        d = body()
        u = db().execute("SELECT * FROM users WHERE email=?", (str(d.get("email", "")).strip().lower(),)).fetchone()
        if not u or not check_password_hash(u["pw_hash"], str(d.get("password", ""))):
            raise ApiError("Invalid email or password", 401)  # same message for both cases
        session["uid"] = u["id"]
        return jsonify(id=u["id"], email=u["email"])

    @app.post("/api/logout")
    def logout():
        session.clear(); return jsonify(ok=True)

    @app.get("/api/me")
    def me():
        u = db().execute("SELECT email FROM users WHERE id=?", (uid(),)).fetchone()
        return jsonify(email=u["email"], **dict(owned_profile()))

    def owned_profile():
        return db().execute("SELECT name,headline,bio,location,website,share_token FROM profiles WHERE user_id=?",
                            (uid(),)).fetchone()

    @app.put("/api/profile")
    def put_profile():
        d = clean(PROFILE_SPEC, body(), partial=True)
        if d:
            db().execute("UPDATE profiles SET " + ",".join(f"{k}=?" for k in d) + " WHERE user_id=?", [*d.values(), uid()])
            log("Updated profile"); db().commit()
        return jsonify(dict(owned_profile()))

    # ---- generic CRUD: skills / projects / certificates -------------------------
    def make_crud(t, cfg):
        def lst():
            sql, args = f"SELECT * FROM {t} WHERE user_id=?", [uid()]
            q = request.args.get("q", "").strip()
            if q:
                sql += " AND (" + " OR ".join(f"{c} LIKE ?" for c in cfg["search"]) + ")"
                args += [f"%{q}%"] * len(cfg["search"])
            return jsonify([dict(r) for r in db().execute(sql + " ORDER BY " + cfg["order"], args)])

        def create():
            d = clean(cfg["spec"], body()); check_dup(t, cfg["dup"], d)
            cols = list(d)
            cur = db().execute(f"INSERT INTO {t}(user_id,{','.join(cols)},created_at) "
                               f"VALUES(?,{','.join('?' * len(cols))},?)", [uid(), *d.values(), now()])
            log(f"Added {cfg['kind']}: {d[cfg['label']]}"); db().commit()
            return jsonify(dict(owned(t, cur.lastrowid))), 201

        def get(rid): return jsonify(dict(owned(t, rid)))

        def update(rid):
            cur = dict(owned(t, rid)); d = clean(cfg["spec"], body(), partial=True)
            check_dup(t, cfg["dup"], {**cur, **d}, exclude=rid)
            if d:
                db().execute(f"UPDATE {t} SET " + ",".join(f"{k}=?" for k in d) + " WHERE id=?", [*d.values(), rid])
                log(f"Updated {cfg['kind']}: {d.get(cfg['label'], cur[cfg['label']])}"); db().commit()
            return jsonify(dict(owned(t, rid)))

        def delete(rid):
            r = owned(t, rid)
            db().execute(f"DELETE FROM {t} WHERE id=?", (rid,))
            log(f"Deleted {cfg['kind']}: {r[cfg['label']]}"); db().commit()
            return "", 204

        for fn, path, m in ((lst, "", "GET"), (create, "", "POST"), (get, "/<int:rid>", "GET"),
                            (update, "/<int:rid>", "PATCH"), (delete, "/<int:rid>", "DELETE")):
            app.add_url_rule(f"/api/{t}{path}", f"{t}_{fn.__name__}", fn, methods=[m])

    for t, cfg in RES.items():
        make_crud(t, cfg)

    # ---- goals + milestones ------------------------------------------------------
    def goal_out(g_row):
        ms = [dict(m) for m in db().execute("SELECT id,title,done FROM milestones WHERE goal_id=? ORDER BY id",
                                            (g_row["id"],))]
        done = sum(m["done"] for m in ms)
        progress = round(100 * done / len(ms)) if ms else 0  # 0 milestones -> 0 %, never divide by zero
        return {**dict(g_row), "milestones": ms, "done": done, "total": len(ms), "progress": progress}

    def clean_ms(raw):
        if not isinstance(raw, list) or len(raw) > 30:
            raise ApiError("milestones must be a list of up to 30 items", 422, {"milestones": "Invalid list"})
        return [clean({"t": ("str", True, 100)}, {"t": m})["t"] for m in raw]

    @app.get("/api/goals")
    def goals_list():
        rows = db().execute("SELECT * FROM goals WHERE user_id=? ORDER BY target_date", (uid(),))
        return jsonify([goal_out(r) for r in rows])

    @app.post("/api/goals")
    def goals_create():
        d = clean(GOAL_SPEC, body()); ms = clean_ms(body().get("milestones", []))
        cur = db().execute("INSERT INTO goals(user_id,title,target_date,created_at) VALUES(?,?,?,?)",
                           (uid(), d["title"], d["target_date"], now()))
        db().executemany("INSERT INTO milestones(goal_id,title) VALUES(?,?)", [(cur.lastrowid, m) for m in ms])
        log(f"Created goal: {d['title']}"); db().commit()
        return jsonify(goal_out(owned("goals", cur.lastrowid))), 201

    @app.get("/api/goals/<int:rid>")
    def goals_get(rid): return jsonify(goal_out(owned("goals", rid)))

    @app.patch("/api/goals/<int:rid>")
    def goals_patch(rid):
        owned("goals", rid); d = clean(GOAL_SPEC, body(), partial=True)
        if d:
            db().execute("UPDATE goals SET " + ",".join(f"{k}=?" for k in d) + " WHERE id=?", [*d.values(), rid])
            db().commit()
        return jsonify(goal_out(owned("goals", rid)))

    @app.delete("/api/goals/<int:rid>")
    def goals_delete(rid):
        r = owned("goals", rid)
        db().execute("DELETE FROM goals WHERE id=?", (rid,)); log(f"Deleted goal: {r['title']}"); db().commit()
        return "", 204

    @app.post("/api/goals/<int:rid>/milestones")
    def ms_add(rid):
        owned("goals", rid); d = clean({"title": ("str", True, 100)}, body())
        db().execute("INSERT INTO milestones(goal_id,title) VALUES(?,?)", (rid, d["title"])); db().commit()
        return jsonify(goal_out(owned("goals", rid))), 201

    def owned_ms(mid):  # ownership is checked through the parent goal
        m = db().execute("SELECT m.*, g.user_id, g.title AS goal FROM milestones m JOIN goals g ON g.id=m.goal_id "
                         "WHERE m.id=? AND g.user_id=?", (mid, uid())).fetchone()
        if not m: raise ApiError("Not found", 404)
        return m

    @app.patch("/api/milestones/<int:mid>")
    def ms_patch(mid):
        m = owned_ms(mid); d = body()
        if "done" in d:  # idempotent: setting the same value twice changes nothing
            new = 1 if d["done"] is True else 0
            if new != m["done"]:
                db().execute("UPDATE milestones SET done=? WHERE id=?", (new, mid))
                if new: log(f"Completed milestone '{m['title']}' in goal '{m['goal']}'")
        if "title" in d:
            db().execute("UPDATE milestones SET title=? WHERE id=?", (clean({"t": ("str", True, 100)}, {"t": d["title"]})["t"], mid))
        db().commit()
        return jsonify(goal_out(owned("goals", m["goal_id"])))

    @app.delete("/api/milestones/<int:mid>")
    def ms_delete(mid):
        m = owned_ms(mid); db().execute("DELETE FROM milestones WHERE id=?", (mid,)); db().commit()
        return jsonify(goal_out(owned("goals", m["goal_id"])))

    # ---- opportunities -----------------------------------------------------------
    def opp_out(r):
        d = dict(r); dl = date.fromisoformat(d["deadline"]); left = (dl - date.today()).days
        d["days_left"] = left; d["overdue"] = left < 0 and d["status"] in OPEN_STATUS
        return d

    @app.get("/api/opportunities")
    def opp_list():
        sql, args = "SELECT * FROM opportunities WHERE user_id=?", [uid()]
        for col in ("type", "status"):
            if request.args.get(col): sql += f" AND {col}=?"; args.append(request.args[col])
        if request.args.get("overdue") == "1":
            sql += " AND deadline<? AND status IN ('Saved','Applied','Interview')"; args.append(date.today().isoformat())
        if request.args.get("q"):
            sql += " AND (title LIKE ? OR organization LIKE ?)"; args += [f"%{request.args['q']}%"] * 2
        order = {"deadline": "deadline ASC", "-deadline": "deadline DESC", "status": "status", "created": "id DESC"}
        sql += " ORDER BY " + order.get(request.args.get("sort"), "deadline ASC")
        return jsonify([opp_out(r) for r in db().execute(sql, args)])

    @app.post("/api/opportunities")
    def opp_create():
        d = clean(OPP_SPEC, body()); d["status"] = d.get("status") or "Saved"
        if date.fromisoformat(d["deadline"]) < date.today():
            raise ApiError("Validation failed", 422, {"deadline": "New opportunities need a deadline of today or later"})
        cols = list(d)
        cur = db().execute(f"INSERT INTO opportunities(user_id,{','.join(cols)},created_at) "
                           f"VALUES(?,{','.join('?' * len(cols))},?)", [uid(), *d.values(), now()])
        db().execute("INSERT INTO status_history(opportunity_id,old_status,new_status,changed_at) VALUES(?,?,?,?)",
                     (cur.lastrowid, None, d["status"], now()))
        log(f"Saved opportunity: {d['title']}"); db().commit()
        return jsonify(opp_out(owned("opportunities", cur.lastrowid))), 201

    @app.get("/api/opportunities/<int:rid>")
    def opp_get(rid): return jsonify(opp_out(owned("opportunities", rid)))

    @app.patch("/api/opportunities/<int:rid>")
    def opp_patch(rid):
        cur = owned("opportunities", rid); d = clean(OPP_SPEC, body(), partial=True)
        if not d.get("status"): d.pop("status", None)  # blank status = unchanged
        if "deadline" in d and d["deadline"] != cur["deadline"] and date.fromisoformat(d["deadline"]) < date.today():
            raise ApiError("Validation failed", 422, {"deadline": "A changed deadline cannot be in the past"})
        if d:
            db().execute("UPDATE opportunities SET " + ",".join(f"{k}=?" for k in d) + " WHERE id=?", [*d.values(), rid])
        if "status" in d and d["status"] != cur["status"]:  # repeated identical update -> no new history row
            db().execute("INSERT INTO status_history(opportunity_id,old_status,new_status,changed_at) VALUES(?,?,?,?)",
                         (rid, cur["status"], d["status"], now()))
            log(f"{cur['title']}: {cur['status']} -> {d['status']}")
        db().commit()
        return jsonify(opp_out(owned("opportunities", rid)))

    @app.delete("/api/opportunities/<int:rid>")
    def opp_delete(rid):
        owned("opportunities", rid); db().execute("DELETE FROM opportunities WHERE id=?", (rid,)); db().commit()
        return "", 204

    @app.get("/api/opportunities/<int:rid>/history")
    def opp_history(rid):
        owned("opportunities", rid)
        rows = db().execute("SELECT old_status,new_status,changed_at FROM status_history WHERE opportunity_id=? ORDER BY id", (rid,))
        return jsonify([dict(r) for r in rows])

    # ---- dashboard + portfolio ---------------------------------------------------
    @app.get("/api/dashboard")
    def dashboard():
        one = lambda sql, *a: db().execute(sql, a).fetchone()[0]
        today = date.today(); soon = (today + timedelta(days=30)).isoformat()
        counts = {t: one(f"SELECT COUNT(*) FROM {t} WHERE user_id=?", uid())
                  for t in ("skills", "projects", "certificates", "goals", "opportunities")}
        rows = lambda sql, *a: [opp_out(r) for r in db().execute(sql, a)]
        base = "SELECT * FROM opportunities WHERE user_id=? AND status IN ('Saved','Applied','Interview') "
        counts["overdue"] = one("SELECT COUNT(*) FROM opportunities WHERE user_id=? AND deadline<? AND status IN ('Saved','Applied','Interview')", uid(), today.isoformat())
        return jsonify(
            counts=counts,
            upcoming=rows(base + "AND deadline>=? AND deadline<=? ORDER BY deadline", uid(), today.isoformat(), soon),
            overdue=rows(base + "AND deadline<? ORDER BY deadline", uid(), today.isoformat()),
            goals=[{k: x[k] for k in ("id", "title", "target_date", "progress", "done", "total")}
                   for x in map(goal_out, db().execute("SELECT * FROM goals WHERE user_id=? ORDER BY target_date", (uid(),)))],
            activity=[dict(r) for r in db().execute("SELECT text,at FROM activity WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid(),))])

    def portfolio_data(user_id):
        q = lambda sql: [dict(r) for r in db().execute(sql, (user_id,))]
        prof = dict(db().execute("SELECT name,headline,bio,location,website FROM profiles WHERE user_id=?", (user_id,)).fetchone())
        goals = [goal_out(r) for r in db().execute("SELECT * FROM goals WHERE user_id=? ORDER BY target_date", (user_id,))]
        return dict(profile=prof, skills=q("SELECT * FROM skills WHERE user_id=? ORDER BY level DESC,name"),
                    projects=q("SELECT * FROM projects WHERE user_id=? ORDER BY id DESC"),
                    certificates=q("SELECT * FROM certificates WHERE user_id=? ORDER BY issue_date DESC"), goals=goals)

    def portfolio_text(p):  # email, opportunities and activity are deliberately never included
        pr, L = p["profile"], []
        L += [pr["name"].upper(), pr["headline"], pr["location"], pr["website"], "", pr["bio"], ""]
        if p["skills"]: L += ["SKILLS"] + [f"  - {s['name']} ({s['level']}/5)" + (f" [{s['tags']}]" if s["tags"] else "") for s in p["skills"]] + [""]
        if p["projects"]: L += ["PROJECTS"] + [f"  - {x['title']}: {x['tech_stack']}\n    {x['github_url']}" for x in p["projects"]] + [""]
        if p["certificates"]: L += ["CERTIFICATES"] + [f"  - {c['title']}, {c['issuer']} ({c['issue_date']})" for c in p["certificates"]] + [""]
        if p["goals"]: L += ["LEARNING GOALS"] + [f"  - {g['title']}: {g['progress']}% ({g['done']}/{g['total']} milestones)" for g in p["goals"]]
        return "\n".join(l for i, l in enumerate(L) if l or (i and L[i - 1])).strip() + "\n"

    @app.get("/api/portfolio")
    def portfolio():
        p = portfolio_data(uid()); share = owned_profile()["share_token"]
        return jsonify(text=portfolio_text(p), share_url=(f"/public/{share}" if share else None))

    @app.get("/api/portfolio/pdf")
    def portfolio_pdf():
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        from xml.sax.saxutils import escape
        p, ss, buf = portfolio_data(uid()), getSampleStyleSheet(), io.BytesIO()
        story = [Paragraph(escape(p["profile"]["name"]), ss["Title"])]
        for line in portfolio_text(p).split("\n")[1:]:
            if not line.strip(): story.append(Spacer(1, 6)); continue
            story.append(Paragraph(escape(line.strip()), ss["Heading2"] if line.isupper() else ss["BodyText"]))
        SimpleDocTemplate(buf, pagesize=A4, title="Portfolio").build(story)
        return Response(buf.getvalue(), mimetype="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=portfolio.pdf"})

    @app.post("/api/share")
    def share():  # enable/disable an unguessable public link
        on = body().get("enabled") is True
        token = secrets.token_urlsafe(16) if on else None
        db().execute("UPDATE profiles SET share_token=? WHERE user_id=?", (token, uid())); db().commit()
        return jsonify(share_url=f"/public/{token}" if token else None)

    @app.get("/public/<token>")
    def public(token):  # no login: only possible with the secret token
        r = db().execute("SELECT user_id FROM profiles WHERE share_token=?", (token,)).fetchone()
        if not r: return Response("Not found", 404, mimetype="text/plain")
        return Response(portfolio_text(portfolio_data(r["user_id"])), mimetype="text/plain; charset=utf-8")

    return app


if __name__ == "__main__":
    create_app().run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", 5000)))
