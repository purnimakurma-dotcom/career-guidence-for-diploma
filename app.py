import sqlite3, json, re
from flask import Flask, request, session, jsonify, g, send_file
from werkzeug.security import generate_password_hash as H, check_password_hash as C

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
DB = "pathpilot.db"
BRANCHES = ["CSE / IT", "ECE", "EEE", "Mechanical", "Civil"]

# ---------- DB helper (all queries are parameterized -> no SQL injection) ----------
def q(sql, a=(), one=False):
    if "d" not in g:
        g.d = sqlite3.connect(DB); g.d.row_factory = sqlite3.Row
    c = g.d.execute(sql, a); g.d.commit(); r = c.fetchall()
    return (r[0] if r else None) if one else r

@app.teardown_appcontext
def close(e):
    d = g.pop("d", None)
    if d: d.close()

# ---------- Questionnaire: (question, [(option, "tags")]) ----------
QS = [
 ("What is your Diploma branch?", [("CSE / IT","it"),("ECE","elec"),("EEE","elec"),("Mechanical","mech core"),("Civil","civil core")]),
 ("Which year are you in?", [("1st year",""),("2nd year",""),("Final year / completed","")]),
 ("How is your academic performance?", [("Above 75%","btech govt"),("60% - 75%",""),("Below 60%","private")]),
 ("Which area interests you the most?", [("Programming & Software","prog it"),("Web Development","web prog design"),("Networking","net"),("Cyber Security","sec net"),("Electronics","elec"),("Mechanical / Automobile","mech core"),("Civil & Construction","civil core"),("Government Jobs","govt"),("Business / Entrepreneurship","biz"),("Design & Creative Work","design")]),
 ("How good are you at programming?", [("Strong","prog logic"),("Basic","prog"),("Never tried","")]),
 ("How comfortable are you with mathematics?", [("Very comfortable","math data btech"),("Average","math"),("Not comfortable","")]),
 ("Your strongest skill?", [("Problem solving","logic prog"),("Communication","comm biz"),("Creativity","design web"),("Leadership","biz govt"),("Teamwork","comm"),("Technical hands-on work","core elec")]),
 ("Which kind of job do you prefer?", [("Government Job","govt"),("Private Job","private it"),("Software / IT Job","it prog"),("Core Engineering Job","core"),("Higher Education","btech"),("Entrepreneurship","biz")]),
 ("Your main goal after diploma?", [("B.Tech through lateral entry","btech"),("Government Job","govt"),("Private Job","private"),("Software Developer","prog it"),("Core Engineering Career","core"),("Start a Business","biz")]),
 ("Which work environment excites you most?", [("Software, coding & desk work","it prog"),("On-site engineering, hardware & manufacturing","core elec"),("Government stability & PSU benefits","govt")]),
 ("Which work style fits you?", [("Solving puzzles & logic problems","logic data"),("Building / fixing things","core"),("Creative, design-oriented work","design"),("Leading people & projects","biz")]),
 ("How do you feel about competitive exams?", [("I enjoy them","govt btech"),("Okay if needed",""),("I prefer to avoid them","private")]),
]
TAGN = dict(prog="programming", web="web development", logic="logical thinking", it="IT/software", private="private-sector jobs",
  net="networking", sec="security", elec="electronics", mech="mechanical", civil="civil/construction", core="core engineering",
  govt="government jobs", biz="business", design="creativity/design", math="mathematics", data="data & analysis",
  comm="communication", btech="higher studies (B.Tech)")

GEN = "Identify skills|Learn fundamentals from trusted resources|Build 2-3 practical projects|Prepare resume & profile|Apply for jobs/internships|Prepare for interviews"
# name, description, skills, education, salary, growth, steps, tag weights
CAREERS = [
 ("Software Development", "Design, build and test software applications.", "Python/Java, DSA, SQL, Git, problem solving",
  "Diploma (CSE/IT) + optional B.Tech", "Rs 2.5L - 4.5L per year (approximate)", "Developer > Senior Developer > Tech Lead",
  "Learn Python basics: variables, data types, conditions, loops, functions, OOP, file handling, basic data structures|Learn web development: HTML (structure), CSS (design), JavaScript (behaviour)|Learn backend: Python + Flask/Django, REST APIs, database concepts|Learn databases: SQL with MySQL/PostgreSQL|Build projects: Student Management System, Career Guidance System, Online Quiz App, Portfolio Website, Job Portal, Expense Tracker|Create GitHub portfolio: push projects with README files and commit regularly|Create resume: skills, projects, education, certifications, achievements, contact info|Apply for jobs/internships on LinkedIn, Internshala, Naukri and company career pages|Prepare for interviews: aptitude, technical, coding, HR questions and communication skills",
  dict(prog=3, logic=2, it=2, private=1)),
 ("Web Development", "Create websites and web apps (frontend, backend or full stack).", "HTML, CSS, JavaScript, React/Flask, Git, UI sense",
  "Diploma + portfolio", "Rs 2L - 4L per year (approximate)", "Web Developer > Full Stack > Architect", "Learn HTML/CSS|Learn JavaScript|Learn a backend (Flask/Node)|Build a portfolio and 3 projects|Publish on GitHub|Apply for internships", dict(web=3, prog=2, design=2)),
 ("Data Analyst", "Collect, clean and analyse data to support decisions.", "Excel, SQL, Python, statistics, visualization",
  "Diploma + certifications", "Rs 2.5L - 4L per year (approximate)", "Analyst > Data Scientist", "Learn Excel & statistics|Learn SQL|Learn Python (pandas)|Build dashboards|Publish projects|Apply for analyst internships", dict(data=3, math=2, logic=2, it=1, prog=1)),
 ("Networking & Cloud", "Manage networks, servers and cloud infrastructure.", "Networking basics, Linux, cloud fundamentals",
  "Diploma + CCNA/cloud certificates", "Rs 2L - 3.5L per year (approximate)", "Technician > Network/Cloud Engineer", "Learn networking basics|Learn Linux|Practice labs|Get a certification|Build home-lab projects|Apply for support roles", dict(net=3, it=1, sec=1)),
 ("Cyber Security", "Protect systems and data from attacks.", "Networking, Linux, security basics, ethical hacking",
  "Diploma + security certificates", "Rs 2.5L - 4L per year (approximate)", "Analyst > Security Engineer", "Learn networking & Linux|Learn security fundamentals|Practice on legal labs/CTFs|Get a certification|Build a write-up portfolio|Apply for SOC/analyst roles", dict(sec=3, net=2, logic=1)),
 ("Electronics & Embedded", "Work on circuits, microcontrollers and automation.", "Circuits, C, microcontrollers, PLC",
  "Diploma (ECE/EEE)", "Rs 2L - 3.5L per year (approximate)", "Technician > Embedded Engineer", "Revise circuit theory|Learn C programming|Learn Arduino/microcontrollers|Build hardware projects|Learn PLC/SCADA|Apply to electronics firms", dict(elec=3, core=1, prog=1)),
 ("Core Engineering (Mech/Civil)", "Site, plant, design and maintenance engineering.", "AutoCAD, core subjects, safety, site skills",
  "Diploma in Mechanical/Civil", "Rs 1.8L - 3.5L per year (approximate)", "Supervisor > Junior Engineer > Manager", "Strengthen core subjects|Learn AutoCAD|Do industrial training|Prepare resume with project|Apply to core companies|Prepare interviews", dict(core=3, mech=2, civil=2)),
 ("Government Jobs", "Technical government posts (JE, technician, PSU, defence).", "Core subjects, reasoning, general awareness, aptitude",
  "Diploma in relevant branch (verify notification)", "As per official pay scale", "Stable promotions and allowances", "Find exams matching your branch|Read official notifications|Study syllabus|Solve previous papers|Apply on official portals|Prepare for tests/interview", dict(govt=3, core=1)),
 ("B.Tech Lateral Entry", "Join B.Tech directly in 2nd year after diploma.", "Mathematics, physics, chemistry, core branch subject",
  "Diploma + qualifying entrance (verify official notice)", "After B.Tech: higher starting packages", "B.Tech > M.Tech / Jobs", "Check official entrance notification|Prepare syllabus|Take mock tests|Apply on official portal|Attend counselling|Choose college & branch", dict(btech=3, math=1)),
 ("Entrepreneurship", "Start your own service or product business.", "Communication, leadership, finance basics",
  "Diploma + business skills", "Variable", "Founder > Business owner", "Find a problem|Validate the idea|Build a small prototype|Learn finance basics|Find first customers|Seek mentors", dict(biz=3, comm=2)),
]
RES = [
 ("official","Education","AICTE","https://www.aicte-india.org"),("official","Education","AP ECET (APSCHE)","https://cets.apsche.ap.gov.in/ECET"),
 ("official","Education","TS ECET","https://ecet.tsche.ac.in"),("official","Jobs","SSC","https://ssc.gov.in"),
 ("official","Jobs","Indian Railways / RRB","https://indianrailways.gov.in"),("official","Jobs","UPSC","https://upsc.gov.in"),
 ("official","Jobs","APPSC","https://psc.ap.gov.in"),("official","Jobs","ISRO","https://www.isro.gov.in"),
 ("official","Jobs","National Career Service","https://www.ncs.gov.in"),("official","Jobs","NAPS Apprenticeship","https://www.apprenticeshipindia.gov.in"),
 ("official","Technology","Python Docs","https://docs.python.org/3/"),("official","Technology","MDN Web Docs","https://developer.mozilla.org"),
 ("official","Technology","Flask Docs","https://flask.palletsprojects.com"),("official","Technology","Django Docs","https://docs.djangoproject.com"),
 ("official","Technology","GitHub","https://github.com"),("official","Technology","Git Docs","https://git-scm.com/doc"),
 ("learning","Programming","Python Tutorial (official)","https://docs.python.org/3/tutorial/"),("learning","Programming","Java Learn","https://dev.java/learn/"),
 ("learning","Programming","C / C++ - GeeksforGeeks","https://www.geeksforgeeks.org"),("learning","Web Development","freeCodeCamp","https://www.freecodecamp.org"),
 ("learning","Web Development","MDN Learn Web","https://developer.mozilla.org/en-US/docs/Learn"),("learning","Web Development","W3Schools HTML/CSS/JS","https://www.w3schools.com"),
 ("learning","Database","W3Schools SQL","https://www.w3schools.com/sql/"),("learning","Database","PostgreSQL Docs","https://www.postgresql.org/docs/"),
 ("learning","Database","MySQL Docs","https://dev.mysql.com/doc/"),("learning","Engineering","NPTEL Courses","https://nptel.ac.in"),
 ("learning","Aptitude","IndiaBIX","https://www.indiabix.com"),("learning","Aptitude","PrepInsta","https://prepinsta.com"),
 ("job","Jobs","Naukri","https://www.naukri.com"),("job","Jobs","LinkedIn Jobs","https://www.linkedin.com/jobs"),
 ("job","Jobs","Indeed India","https://in.indeed.com"),("job","Jobs","Internshala","https://internshala.com"),("job","Jobs","Freshersworld","https://www.freshersworld.com"),
 ("youtube","YouTube","Python for beginners (search)","https://www.youtube.com/results?search_query=python+for+beginners"),
 ("youtube","YouTube","AP ECET preparation (search)","https://www.youtube.com/results?search_query=AP+ECET+preparation"),
 ("youtube","YouTube","SSC JE preparation (search)","https://www.youtube.com/results?search_query=SSC+JE+preparation"),
 ("youtube","YouTube","Web development full course (search)","https://www.youtube.com/results?search_query=web+development+full+course"),
 ("youtube","YouTube","Resume & interview tips (search)","https://www.youtube.com/results?search_query=resume+interview+tips+freshers"),
]

def init():
    with app.app_context():
        q("""create table if not exists users(id integer primary key, name text, email text unique, pw text, branch text, admin int default 0);""")
        q("""create table if not exists results(id integer primary key, uid int, answers text, scores text, tags text, created text default current_timestamp);""")
        q("""create table if not exists careers(id integer primary key, name text unique, description text, skills text, education text, salary text, growth text, steps text, tags text);""")
        q("""create table if not exists resources(id integer primary key, kind text, category text, title text, url text);""")
        if not q("select 1 from careers"):
            for c in CAREERS: q("insert into careers(name,description,skills,education,salary,growth,steps,tags) values(?,?,?,?,?,?,?,?)", c[:7] + (json.dumps(c[7]),))
            for r in RES: q("insert into resources(kind,category,title,url) values(?,?,?,?)", r)
            q("insert into users(name,email,pw,branch,admin) values(?,?,?,?,1)", ("Admin", "admin@pathpilot.com", H("admin123"), "CSE / IT"))

# ---------- helpers ----------
def user():
    return q("select * from users where id=?", (session.get("uid"),), True) if session.get("uid") else None
def need(admin=False):
    u = user()
    return u if u and (u["admin"] or not admin) else None
def clean(s, n=200): return re.sub(r"[<>]", "", str(s or "")).strip()[:n]
def err(m, c=400): return jsonify(error=m), c

def score(answers):
    t = {}
    for qi, oi in enumerate(answers):
        for tag in QS[qi][1][oi][1].split(): t[tag] = t.get(tag, 0) + 1
    out = []
    for c in q("select * from careers"):
        w = json.loads(c["tags"]); s = sum(t.get(k, 0) * v for k, v in w.items())
        out.append([c["name"], max(5, min(98, round(100 * s / (sum(w.values()) * 2))))])
    return sorted(out, key=lambda x: -x[1]), t

# ---------- routes ----------
@app.route("/")
def home(): return send_file("index.html")

@app.post("/api/register")
def register():
    d = request.get_json(silent=True) or {}
    name, email, pw, br = clean(d.get("name"), 60), clean(d.get("email"), 100).lower(), str(d.get("password", "")), d.get("branch")
    if len(name) < 2: return err("Enter your full name")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email): return err("Enter a valid email")
    if len(pw) < 6: return err("Password must be at least 6 characters")
    if pw != d.get("confirm"): return err("Passwords do not match")
    if br not in BRANCHES: return err("Select your diploma branch")
    if q("select 1 from users where email=?", (email,)): return err("Email already registered")
    q("insert into users(name,email,pw,branch) values(?,?,?,?)", (name, email, H(pw), br))
    return jsonify(ok=1)

@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    u = q("select * from users where email=?", (clean(d.get("email")).lower(),), True)
    if not u or not C(u["pw"], str(d.get("password", ""))): return err("Invalid email or password", 401)
    session.clear(); session["uid"] = u["id"]
    return jsonify(ok=1)

@app.post("/api/logout")
def logout(): session.clear(); return jsonify(ok=1)

@app.get("/api/me")
def me():
    u = user()
    if not u: return jsonify(user=None)
    done = bool(q("select 1 from results where uid=?", (u["id"],)))
    return jsonify(user=dict(name=u["name"], email=u["email"], branch=u["branch"], admin=bool(u["admin"]), done=done))

@app.get("/api/questions")
def questions(): return jsonify([dict(q=a, o=[x[0] for x in b]) for a, b in QS])

@app.get("/api/careers")
def careers(): return jsonify([dict(r) for r in q("select * from careers")])

@app.get("/api/resources")
def resources(): return jsonify([dict(r) for r in q("select * from resources order by kind,category")])

@app.post("/api/submit")
def submit():
    u = need()
    if not u: return err("Login required", 401)
    a = (request.get_json(silent=True) or {}).get("answers")
    if not isinstance(a, list) or len(a) != len(QS) or any(not isinstance(x, int) or not 0 <= x < len(QS[i][1]) for i, x in enumerate(a)):
        return err("Please answer all questions")
    sc, t = score(a)
    q("insert into results(uid,answers,scores,tags) values(?,?,?,?)", (u["id"], json.dumps(a), json.dumps(sc), json.dumps(t)))
    return jsonify(ok=1)

@app.get("/api/result")
def result():
    u = need()
    if not u: return err("Login required", 401)
    r = q("select * from results where uid=? order by id desc limit 1", (u["id"],), True)
    if not r: return err("No assessment yet", 404)
    sc, t = json.loads(r["scores"]), json.loads(r["tags"])
    top = dict(q("select * from careers where name=?", (sc[0][0],), True)); top["pct"] = sc[0][1]
    top["steps"] = top["steps"].split("|")
    m = [TAGN[k] for k, _ in sorted(t.items(), key=lambda x: -x[1]) if k in TAGN and k in json.loads(top["tags"])][:4]
    why = ("You showed strong interest in " + ", ".join(m) + f". These match the profile of {top['name']}, making it your best fit.") if m else f"Your overall answers match {top['name']} best."
    return jsonify(top=top, why=why, others=sc[1:4])

# ---------- admin ----------
@app.get("/api/admin/data")
def admin_data():
    if not need(True): return err("Admin only", 403)
    us = [dict(r) for r in q("select id,name,email,branch from users where admin=0")]
    rs = [dict(r) for r in q("select r.id,u.name,r.scores,r.created from results r join users u on u.id=r.uid order by r.id desc")]
    dist = {}
    for r in rs: n = json.loads(r["scores"])[0][0]; dist[n] = dist.get(n, 0) + 1
    for r in rs: r["top"] = json.loads(r.pop("scores"))[0]
    return jsonify(users=us, results=rs, dist=dist)

@app.post("/api/admin/career")
def admin_career():
    if not need(True): return err("Admin only", 403)
    d = request.get_json(silent=True) or {}
    try: tags = json.loads(d.get("tags", "")); assert isinstance(tags, dict)
    except Exception: return err('Tags must be JSON like {"prog":3}')
    f = [clean(d.get(k), 2000) for k in ("name", "description", "skills", "education", "salary", "growth", "steps")]
    if not f[0]: return err("Name required")
    q("""insert into careers(name,description,skills,education,salary,growth,steps,tags) values(?,?,?,?,?,?,?,?)
         on conflict(name) do update set description=excluded.description,skills=excluded.skills,education=excluded.education,
         salary=excluded.salary,growth=excluded.growth,steps=excluded.steps,tags=excluded.tags""", tuple(f) + (json.dumps(tags),))
    return jsonify(ok=1)

@app.post("/api/admin/resource")
def admin_resource():
    if not need(True): return err("Admin only", 403)
    d = request.get_json(silent=True) or {}
    url = clean(d.get("url"), 300)
    if d.get("kind") not in ("official", "learning", "job", "youtube") or not re.match(r"^https?://", url): return err("Valid kind and http(s) URL required")
    q("insert into resources(kind,category,title,url) values(?,?,?,?)", (d["kind"], clean(d.get("category"), 50), clean(d.get("title"), 100), url))
    return jsonify(ok=1)

init()
if __name__ == "__main__":
    app.run(debug=True)
