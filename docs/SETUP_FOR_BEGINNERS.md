# Beginner's Setup Guide

This guide assumes you have never run a web project before. It explains what each step does, not only what to type.

## Part 1: Understand what you are running

**The big picture.** This project is a small website with two halves:
- **The backend** (`app.py`) is a Python program that runs on your computer. It stores data and applies the rules (for example "a link must start with http").
- **The frontend** (`static/index.html`) is the page you see in your browser. It shows buttons and forms and asks the backend for data.

**How they talk.** When you click "Add skill", the page sends a message to the backend ("please save this skill"). The backend checks it, saves it in the database file `tracker.db`, and replies. The page then shows the result. Because the data is saved in a file, it is still there after you close and reopen the app.

**What each file is for**
| File | What it does |
|---|---|
| `app.py` | the backend: all rules and all data handling |
| `schema.sql` | describes the database tables; read automatically on first start |
| `static/index.html` | the whole user interface |
| `seed.py` | fills the app with example data for demos |
| `tests/test_api.py` | automatic checks that prove the rules work |
| `requirements.txt` | the list of extra Python tools the project needs |
| `Procfile`, `render.yaml` | instructions for the website host (used only when putting it online) |
| `docs/` | the guide, this file and the PDF |

**Key words**
- **Terminal / command prompt**: a window where you type commands instead of clicking.
- **Folder / directory**: the same thing as a folder in File Explorer or Finder.
- **Virtual environment (venv)**: a private box of Python tools for one project, so projects do not interfere with each other.
- **pip**: Python's installer for extra tools.
- **Server**: a program that waits for requests and answers them. `python app.py` starts one on your own computer.
- **localhost / 127.0.0.1**: the address that means "this computer".
- **Port (5000)**: like a door number; the app listens at door 5000.

## Part 2: Install what you need

### 2.1 Python
1. Go to python.org, click Downloads, and install the latest Python 3 (3.10 or newer).
2. **Windows only:** on the first installer screen, tick **"Add python.exe to PATH"** before clicking Install. If you miss this, commands later will say "python is not recognized".
3. Check it worked. Open a terminal (see 2.2) and type:
   ```
   python --version
   ```
   You should see something like `Python 3.12.3`. On Mac and Linux the command may be `python3` instead; use it everywhere this guide says `python`.

### 2.2 Opening a terminal
- **Windows:** press the Windows key, type `cmd` (or `PowerShell`), press Enter.
- **Mac:** press Cmd+Space, type `Terminal`, press Enter.
- **Linux:** press Ctrl+Alt+T.

### 2.3 A code editor (optional but helpful)
Install Visual Studio Code (code.visualstudio.com) so you can read and edit the files. Open the project with File, then Open Folder.

### 2.4 Git (only needed to upload to GitHub)
Install from git-scm.com with all default options. Check with `git --version`.

## Part 3: Put the project in the right place

1. Create a folder called `skill-tracker` somewhere easy, for example in Documents.
2. Put the files in it so it looks exactly like this. Names must match, and `index.html` must be inside `static`, the test file inside `tests`.
   ```
   skill-tracker/
     app.py
     schema.sql
     seed.py
     requirements.txt
     Procfile
     render.yaml
     README.md
     .gitignore
     static/index.html
     tests/test_api.py
     docs/GUIDE.md
     docs/build_pdf.py
     docs/SETUP_FOR_BEGINNERS.md
   ```
3. Open a terminal **inside** that folder. Easiest way: in the terminal, type `cd ` (with a space), drag the folder into the terminal window, press Enter. Check with `dir` (Windows) or `ls` (Mac/Linux): you should see `app.py` in the list. If you do not, you are in the wrong folder, and almost every later error comes from this.

## Part 4: Install the project's tools

### 4.1 Create a virtual environment
```
python -m venv venv
```
This makes a folder called `venv`. Nothing visible happens; that is normal.

### 4.2 Turn it on ("activate")
- Windows (Command Prompt): `venv\Scripts\activate`
- Windows (PowerShell): `venv\Scripts\Activate.ps1`  (if it is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again)
- Mac/Linux: `source venv/bin/activate`

Success looks like `(venv)` appearing at the start of your terminal line. You must activate it again every time you open a new terminal.

### 4.3 Install the requirements
```
pip install -r requirements.txt
```
This reads `requirements.txt` and downloads Flask (the web framework), reportlab (makes PDFs) and gunicorn (used only for online hosting). Wait until you see "Successfully installed".

## Part 5: Prove it works with the tests
```
python -m unittest discover -s tests -v
```
This runs 18 automatic checks. Each line names a rule being tested (for example duplicate skills being rejected). The end should say `OK`. The tests use temporary databases, so they never touch your real data. If something fails, read the first error line: it usually names a missing file or tool.

## Part 6: Add example data and start the app

1. Create the demo data (optional):
   ```
   python seed.py
   ```
   This makes the file `tracker.db` and an account: **demo@example.com** with password **demo12345**, plus skills, a project, goals and opportunities.
2. Start the server:
   ```
   python app.py
   ```
   You will see lines like `Running on http://127.0.0.1:5000`. Leave this terminal open; closing it stops the app.
3. Open a browser and go to **http://127.0.0.1:5000**.
4. Log in with the demo account, or click **Create account** to make your own.
5. To stop the app, click the terminal and press **Ctrl+C**.

## Part 7: Walk through the app (what happens behind each click)

| You do this | What the app does |
|---|---|
| Create account | checks email and password length, stores a scrambled (hashed) password, logs you in with a cookie |
| Add a skill (level 1 to 5) | the backend validates it, refuses duplicates, saves it, adds a line to Recent activity |
| Type `notaurl` as a project link | the backend replies with an error and the form shows it under the field |
| Create a goal with milestones | goal and milestones are saved; progress starts at 0% |
| Tick a milestone | the backend counts ticked / total; 1 of 4 shows 25%, and unticking lowers it |
| Add an opportunity with a past date | rejected: new deadlines must be today or later |
| Change an opportunity's status | saved with a timestamp; the History button lists every change |
| Overdue badge | shown when the deadline has passed and the status is still Saved, Applied or Interview |
| Portfolio, Download PDF | builds a summary without your email or opportunities and turns it into a PDF |
| Share link | creates a secret web address anyone can read; Stop sharing deletes it |
| Close the app and start again | your data is still there because it is in `tracker.db` |

Another user can never see your data: every database lookup includes your user id.

## Part 8: Upload to GitHub

GitHub stores your code online. It does **not** run the app; it only holds the files.

1. In your browser, sign in at github.com, click **+**, then **New repository**. Name it `skill-opportunity-tracker`, choose **Public**, do **not** tick "Add a README", and click **Create repository**.
2. In your project terminal (inside `skill-tracker`) run these one at a time:
   ```
   git init
   git add .
   git commit -m "Student Skill and Opportunity Tracker"
   git branch -M main
   git remote add origin https://github.com/akshatshukla509-code/skill-opportunity-tracker.git
   git push -u origin main
   ```
   What they mean: `init` starts tracking, `add .` selects all files, `commit` takes a saved snapshot, `branch -M main` names the main line of work, `remote add` links your folder to the GitHub page, `push` uploads.
3. Git may say "Please tell me who you are". Run these once, then repeat the commit:
   ```
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
4. When asked to sign in, GitHub no longer accepts your normal password in the terminal. Create a **personal access token**: GitHub, Settings, Developer settings, Personal access tokens, Tokens (classic), Generate new token, tick `repo`, and use the token as the password.
5. Before pushing, run `git status`. The files `tracker.db` and `.secret_key` must **not** be listed; `.gitignore` hides them. They contain data and a secret.
6. Refresh the GitHub page: your files should appear. Only you can change them, because only your account has write access.

## Part 9: Put it on the internet (Render)

Render is a free service that runs your app on a public address.

1. Go to render.com and choose **Sign in with GitHub**.
2. Click **New**, then **Blueprint**, select your repository, and approve.
3. Render reads `render.yaml`: it installs the requirements, creates a private `SECRET_KEY` (used to sign login cookies), and starts the app with gunicorn (a production-grade server; `python app.py` is for your own computer only).
4. After a few minutes, Render shows your public link, like `https://skill-tracker.onrender.com`. Share it with anyone.
5. To change the site later: edit files, then run `git add .`, `git commit -m "describe change"`, `git push`. Render redeploys automatically.

Free-plan behaviour you should expect: the site sleeps after about 15 minutes idle (the first visit takes up to a minute), and saved data can be wiped when it restarts. Mention this as a limitation in your README.

## Part 10: When something goes wrong

| Message or symptom | Meaning and fix |
|---|---|
| `python is not recognized` | Python is not on PATH. Reinstall and tick "Add to PATH", or try `py` or `python3` |
| `No module named flask` | the venv is not active or step 4.3 did not finish. Activate it and run pip install again |
| `can't open file app.py` | you are in the wrong folder. Use `cd` to enter `skill-tracker` |
| `FileNotFoundError: schema.sql` | `schema.sql` is not next to `app.py` |
| Browser shows Not found at `/` | `index.html` is not inside the `static` folder |
| `Address already in use` | something else uses port 5000 (common on Mac). Run `PORT=5001 python app.py` (Mac/Linux) or `set PORT=5001` then `python app.py` (Windows), and open port 5001 |
| `Demo user already exists` | you already seeded. Delete `tracker.db` and run `python seed.py` again |
| Login page appears again suddenly | the secret key file changed or was deleted; just log in again |
| `git push` rejected or asks for login repeatedly | use a personal access token, not your password |
| Site works locally but not on Render | open the Render dashboard, then Logs, and read the last error; it is nearly always a missing file or a typo in the folder layout |

## Part 11: What to practise before presenting
1. Explain the path of one click: button, `fetch`, API route, validation, database, response, screen update.
2. Find where a rule lives: search `app.py` for `valid_url` (links), `check_dup` (duplicates) and `progress` (goal percentage).
3. Make one small change and test it. Example: in `opp_create`, change `< date.today()` so deadlines must be strictly after today, then run the tests and watch which one fails and why.
4. Be ready to describe how you tested: the 18 tests cover validation, goal maths, status changes, ownership and persistence.
