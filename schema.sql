-- Student Skill & Opportunity Tracker: SQLite schema (every child row carries user_id for ownership checks)
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, pw_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS profiles(
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL, headline TEXT DEFAULT '', bio TEXT DEFAULT '', location TEXT DEFAULT '',
  website TEXT DEFAULT '', share_token TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS skills(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5), tags TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_skill ON skills(user_id, lower(name));
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, description TEXT DEFAULT '', tech_stack TEXT DEFAULT '',
  github_url TEXT NOT NULL, demo_url TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_project ON projects(user_id, lower(title), lower(github_url));
CREATE TABLE IF NOT EXISTS certificates(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, issuer TEXT NOT NULL, issue_date TEXT NOT NULL, credential_url TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cert ON certificates(user_id, lower(title), lower(issuer));
CREATE TABLE IF NOT EXISTS goals(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, target_date TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS milestones(
  id INTEGER PRIMARY KEY, goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
  title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0 CHECK(done IN (0,1)));
CREATE TABLE IF NOT EXISTS opportunities(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL, organization TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('Internship','Hackathon','Workshop','Course')),
  deadline TEXT NOT NULL, link TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'Saved' CHECK(status IN ('Saved','Applied','Interview','Completed','Rejected')),
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS status_history(
  id INTEGER PRIMARY KEY, opportunity_id INTEGER NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  old_status TEXT, new_status TEXT NOT NULL, changed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activity(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  text TEXT NOT NULL, at TEXT NOT NULL);
