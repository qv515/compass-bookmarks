#!/usr/bin/env python3
"""
STR Bookmarks — Internal resource directory.
Reads from a Google Sheet via service account. Google OAuth login gated
to @roofstock.com + whitelist. Auto-refreshes bookmarks every hour.
"""
import os, sys, json, urllib.request, urllib.parse, time, secrets, threading

from flask import Flask, request, jsonify, session, redirect, url_for

# --- Configuration ---
SHEET_ID = "1mXmOaTeDXEfelXB8gBe98R1lvCZPvZQNGpCeCX_HFv4"

# --- Google OAuth Config ---
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))
ALLOWED_DOMAINS = ["roofstock.com", "vuestay.com"]
WHITELIST_SHEET_ID = "1hKIa2MTyG3ZBXPZ0g5UU8H4FdQyDEiO73kd6OgMFrAE"
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL") or ""

# --- Service Account ---
SERVICE_ACCOUNT_INFO = None
sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
if sa_json:
    try:
        SERVICE_ACCOUNT_INFO = json.loads(sa_json)
        print("Service account loaded", flush=True)
    except:
        print("WARNING: Failed to parse GOOGLE_SERVICE_ACCOUNT", flush=True)

# --- In-memory cache ---
BOOKMARKS = []
BOOKMARKS_LOCK = threading.Lock()
LAST_FETCH_ERROR = None
LAST_FETCH_TIME = None

# --- Logo ---
LOGO_B64 = ""
logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_b64.txt")
if os.path.exists(logo_path):
    with open(logo_path) as f:
        LOGO_B64 = f.read().strip()
        print(f"Logo loaded: {len(LOGO_B64)} chars", flush=True)
else:
    print("Logo file not found", flush=True)

# --- Flask ---
app = Flask(__name__)
app.secret_key = SESSION_SECRET

# ==============================================================
# Google Sheets helpers
# ==============================================================

def _sheets_api_read(spreadsheet_id, sheet_range):
    """Read a range from Google Sheets using service account JWT auth (no extra deps)."""
    global LAST_FETCH_ERROR
    if not SERVICE_ACCOUNT_INFO:
        return None
    try:
        import jwt
        now = int(time.time())
        claims = {
            "iss": SERVICE_ACCOUNT_INFO["client_email"],
            "sub": SERVICE_ACCOUNT_INFO["client_email"],
            "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600
        }
        assertion = jwt.encode(claims, SERVICE_ACCOUNT_INFO["private_key"], algorithm="RS256")
        token_data = urllib.parse.urlencode({
            "assertion": assertion,
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer"
        }).encode()
        treq = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(treq, timeout=15) as tresp:
            tokens = json.loads(tresp.read().decode())
        token = tokens.get("access_token")
        if not token:
            return None
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{urllib.parse.quote(sheet_range)}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except ImportError as e:
        LAST_FETCH_ERROR = f"pyjwt not installed: {e}"
        print(LAST_FETCH_ERROR, flush=True)
        return None
    except Exception as e:
        LAST_FETCH_ERROR = f"Sheets API error: {e}"
        print(LAST_FETCH_ERROR, flush=True)
        return None

def fetch_whitelist():
    """Read whitelist emails from the whitelist sheet."""
    result = _sheets_api_read(WHITELIST_SHEET_ID, "list!A:A")
    if not result:
        return set()
    emails = set()
    for row in result.get("values", []):
        if row and row[0] and "@" in row[0]:
            emails.add(row[0].strip().lower())
    print(f"Whitelist: {len(emails)} emails loaded", flush=True)
    return emails

def fetch_bookmarks():
    """Read the bookmarks sheet and return approved items grouped by section."""
    result = _sheets_api_read(SHEET_ID, "Sheet1!A1:F200")
    if not result:
        return {}
    rows = result.get("values", [])
    if not rows:
        return {}
    # Row 0 = header
    bookmarks = []
    for row in rows[1:]:
        if len(row) < 5:
            continue
        approved = row[4].strip().upper() if len(row) > 4 else "FALSE"
        if approved != "TRUE":
            continue
        bookmarks.append({
            "section": (row[0] or "").strip(),
            "title": (row[1] or "").strip(),
            "link": (row[2] or "").strip(),
            "owner": (row[3] or "").strip() if len(row) > 3 else "",
            "description": (row[5] or "").strip() if len(row) > 5 else ""
        })
    # Group by section, preserving insertion order
    sections = {}
    for b in bookmarks:
        sec = b["section"] or "Other"
        sections.setdefault(sec, []).append(b)
    return sections

def is_allowed(email, whitelist):
    if not email:
        return False
    if email.lower() in whitelist:
        return True
    for domain in ALLOWED_DOMAINS:
        if email.endswith(f"@{domain}"):
            return True
    return False

# ==============================================================
# Data refresh
# ==============================================================

WHITELIST = set()

def refresh_all():
    global BOOKMARKS, WHITELIST
    try:
        sections = fetch_bookmarks()
        with BOOKMARKS_LOCK:
            BOOKMARKS = list(sections.items())  # list of (section_name, [items])
        print(f"Bookmarks: {sum(len(v) for v in sections.values())} items across {len(sections)} sections", flush=True)
    except Exception as e:
        print(f"Bookmarks refresh error: {e}", flush=True)
    try:
        WHITELIST = fetch_whitelist()
    except Exception as e:
        print(f"Whitelist refresh error: {e}", flush=True)

# Initial load
refresh_all()

# Background refresh thread — every hour
def refresh_loop():
    while True:
        time.sleep(3600)
        refresh_all()

t = threading.Thread(target=refresh_loop, daemon=True)
t.start()

# Whitelist refresher
def whitelist_refresh_loop():
    global WHITELIST
    while True:
        time.sleep(300)
        try:
            WHITELIST = fetch_whitelist()
        except Exception as e:
            print(f"Whitelist refresh error: {e}", flush=True)
            time.sleep(60)

tw = threading.Thread(target=whitelist_refresh_loop, daemon=True)
tw.start()

# ==============================================================
# Auth routes
# ==============================================================

@app.route("/login")
def login():
    if not GOOGLE_CLIENT_ID:
        return "Google login not configured", 500
    redir = url_for("callback", _external=True)
    auth_url = (
        "https://accounts.google.com/o/oauth2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}&redirect_uri={urllib.parse.quote(redir)}"
        "&response_type=code&scope=openid%20email&access_type=online"
    )
    return redirect(auth_url)

@app.route("/login/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing auth code", 400
    try:
        redir = url_for("callback", _external=True)
        data = urllib.parse.urlencode({
            "code": code, "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redir, "grant_type": "authorization_code"
        }).encode()
        treq = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(treq) as resp:
            tokens = json.loads(resp.read().decode())
        id_token_str = tokens.get("id_token")
        if not id_token_str:
            return "No ID token", 400
        vreq = urllib.request.Request(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token_str}")
        with urllib.request.urlopen(vreq) as vresp:
            info = json.loads(vresp.read().decode())
        email = info.get("email", "")
        if not email:
            return "Email not provided", 400
        if not is_allowed(email, WHITELIST):
            encoded = urllib.parse.quote(email)
            return f"""<html><body style="background:#0F172A;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:1rem">
            <div style="text-align:center;max-width:420px;width:100%">
            <img src="data:image/png;base64,{LOGO_B64}" alt="Casago" style="max-width:200px;margin-bottom:2rem">
            <h1 style="font-size:1.1rem;font-weight:600;color:#F1F5F9;margin-bottom:0.5rem">{email} is not authorized</h1>
            <p style="color:#94a3b8;margin-bottom:1.5rem;font-size:0.9rem">Request access and an admin will review your request.</p>
            <button onclick="fetch('/request-access?email={encoded}',{{method:'POST'}}).then(r=>r.text()).then(t=>document.getElementById('msg').textContent=t)" style="padding:0.75rem 2.5rem;background:#438ECA;color:#0F172A;border:0;border-radius:8px;font-weight:600;font-size:0.95rem;cursor:pointer">Request Access</button>
            <p id="msg" style="color:#22c55e;margin-top:1rem;font-size:0.85rem"></p>
            <a href="/" style="display:inline-block;margin-top:1rem;color:#64748b;text-decoration:none;font-size:0.85rem">&larr; Back to sign in</a>
            </div></body></html>""", 403
        session["user"] = {"email": email, "name": info.get("name", email)}
        return redirect("/")
    except Exception as e:
        return f"Auth error: {e}", 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/request-access", methods=["POST"])
def request_access():
    email = request.args.get("email", "")
    if not email:
        return "No email provided", 400
    if SLACK_WEBHOOK:
        try:
            payload = json.dumps({"text": f":door: Access request from {email}\nAdd to whitelist: https://docs.google.com/spreadsheets/d/{WHITELIST_SHEET_ID}/edit"}).encode()
            req = urllib.request.Request(SLACK_WEBHOOK, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except:
            pass
    return "Request sent! An admin will review shortly."

@app.route("/health")
def health():
    return "ok", 200

@app.route("/refresh")
def refresh():
    """Cron-job hits this every hour to force a data refresh from the sheet."""
    refresh_all()
    with BOOKMARKS_LOCK:
        total = sum(len(items) for _, items in BOOKMARKS)
    return jsonify({"status": "ok", "sections": len(BOOKMARKS), "bookmarks": total})

@app.route("/debug")
def debug():
    """Check service account, whitelist status, bookmark count."""
    info = {
        "service_account_loaded": SERVICE_ACCOUNT_INFO is not None,
        "service_account_email": SERVICE_ACCOUNT_INFO.get("client_email", "") if SERVICE_ACCOUNT_INFO else "",
        "whitelist_count": len(WHITELIST),
        "whitelist_emails": sorted(WHITELIST) if WHITELIST else [],
        "slack_configured": bool(SLACK_WEBHOOK),
        "bookmark_sections": len(BOOKMARKS),
        "last_fetch_error": LAST_FETCH_ERROR,
    }
    return f"<pre>{json.dumps(info, indent=2)}</pre>"

# ==============================================================
# API — JSON data for the frontend
# ==============================================================

@app.route("/api/bookmarks")
def api_bookmarks():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    with BOOKMARKS_LOCK:
        data = []
        for section, items in BOOKMARKS:
            data.append({"section": section, "items": items})
    return jsonify({"sections": data, "user": user.get("email", "")})

# ==============================================================
# Main page — full HTML app
# ==============================================================

@app.before_request
def check_auth():
    allowed_routes = {"login", "callback", "static", "request_access", "debug", "health", "refresh", "api_bookmarks"}
    if request.endpoint in allowed_routes or request.path.startswith("/login"):
        return
    if not session.get("user"):
        return LOGIN_PAGE, 401

@app.route("/dashboard")
def dashboard():
    user = session.get("user", {})
    user_email = user.get("email", "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard · STR Bookmarks</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0F172A;
    color: #F1F5F9;
    min-height: 100vh;
  }}
  .header {{
    position: sticky; top: 0; z-index: 100;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(16px) saturate(1.5);
    -webkit-backdrop-filter: blur(16px) saturate(1.5);
    border-bottom: 1px solid #334155;
    padding: 0 2rem;
  }}
  .header-inner {{
    max-width: 1100px; margin: 0 auto;
    display: flex; align-items: center; justify-content: space-between;
    height: 64px;
  }}
  .logo {{ display: flex; align-items: center; }}
  .logo-img {{ max-height: 28px; width: auto; }}
  .header-nav {{ display: flex; align-items: center; gap: 0.25rem; }}
  .nav-btn {{
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.4rem 0.85rem; border-radius: 8px;
    font-size: 0.8rem; font-weight: 500;
    color: #94A3B8; text-decoration: none; transition: all 0.15s;
  }}
  .nav-btn:hover {{ background: #1F2937; color: #CBD5E1; }}
  .nav-btn.active {{ background: #1F2937; color: #438ECA; }}
  .nav-btn svg {{ width: 16px; height: 16px; flex-shrink: 0; }}
  .header-actions {{ display: flex; align-items: center; gap: 1rem; }}
  .user-email {{ font-size: 0.8rem; color: #94A3B8; }}
  .btn-logout {{
    padding: 0.4rem 1rem; border-radius: 6px;
    font-size: 0.8rem; font-weight: 500;
    background: transparent; color: #94A3B8;
    border: 1px solid #334155; cursor: pointer;
    transition: all 0.2s; text-decoration: none;
  }}
  .btn-logout:hover {{ background: #334155; color: #F1F5F9; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 2.5rem 2rem 4rem; }}
  .wip {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 4rem 2rem; text-align: center;
  }}
  .wip-icon {{ font-size: 3rem; margin-bottom: 1rem; opacity: 0.6; }}
  .wip h2 {{ font-size: 1.5rem; font-weight: 700; color: #CBD5E1; margin-bottom: 0.5rem; }}
  .wip p {{ font-size: 0.9rem; color: #64748B; }}
</style>
</head>
<body>
<div class="header">
  <div class="header-inner">
    <div class="logo">
      <img src="data:image/png;base64,{LOGO_B64}" alt="Casago" class="logo-img">
    </div>
    <div class="header-nav">
      <a href="/" class="nav-btn">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
        Bookmarks
      </a>
      <a href="/dashboard" class="nav-btn active">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        Dashboard
      </a>
    </div>
    <div class="header-actions">
      <span class="user-email">{user_email}</span>
      <a href="/logout" class="btn-logout">Sign out</a>
    </div>
  </div>
</div>
<div class="container">
  <div class="wip">
    <div class="wip-icon">🚧</div>
    <h2>Work in Progress</h2>
    <p>This dashboard is coming soon.</p>
  </div>
</div>
</body>
</html>"""

@app.route("/")
def index():
    user = session.get("user", {})
    user_email = user.get("email", "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>STR Bookmarks</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0F172A;
    color: #F1F5F9;
    min-height: 100vh;
  }}
  ::selection {{ background: #438ECA44; color: #438ECA; }}

  /* Scrollbar */
  ::-webkit-scrollbar {{ width: 6px; }}
  ::-webkit-scrollbar-track {{ background: #0F172A; }}
  ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
  ::-webkit-scrollbar-thumb:hover {{ background: #4B5563; }}

  /* Header */
  .header {{
    position: sticky; top: 0; z-index: 100;
    background: rgba(12, 1, 56, 0.85);
    backdrop-filter: blur(16px) saturate(1.5);
    -webkit-backdrop-filter: blur(16px) saturate(1.5);
    border-bottom: 1px solid #334155;
    padding: 0 2rem;
  }}
  .header-inner {{
    max-width: 1100px; margin: 0 auto;
    display: flex; align-items: center; justify-content: space-between;
    height: 64px;
  }}
  .logo {{
    display: flex; align-items: center;
  }}
  .logo-img {{ max-height: 28px; width: auto; }}
  .header-actions {{
    display: flex; align-items: center; gap: 1rem;
  }}
  .user-email {{
    font-size: 0.8rem; color: #CBD5E1;
  }}
  .btn-logout {{
    padding: 0.4rem 1rem; border-radius: 6px;
    font-size: 0.8rem; font-weight: 500;
    background: transparent; color: #94a3b8;
    border: 1px solid #334155; cursor: pointer;
    transition: all 0.2s;
    text-decoration: none;
  }}
  .btn-logout:hover {{
      background: #334155; color: #F1F5F9;
    }}

    /* Nav */
    .header-nav {{
      display: flex; align-items: center; gap: 0.25rem;
    }}
    .nav-btn {{
      display: inline-flex; align-items: center; gap: 0.4rem;
      padding: 0.4rem 0.85rem;
      border-radius: 8px;
      font-size: 0.8rem; font-weight: 500;
      color: #94A3B8;
      text-decoration: none;
      transition: all 0.15s;
    }}
    .nav-btn:hover {{
      background: #1F2937; color: #CBD5E1;
    }}
    .nav-btn.active {{
      background: #1F2937; color: #438ECA;
    }}
    .nav-btn svg {{
      width: 16px; height: 16px;
      flex-shrink: 0;
    }}

    /* Main content */
  .container {{
    max-width: 1100px; margin: 0 auto; padding: 2.5rem 2rem 4rem;
  }}
  .hero {{
    margin-bottom: 3rem;
  }}
  .hero h1 {{
    font-size: 2.5rem; font-weight: 800; letter-spacing: -0.03em;
    color: #438ECA;
    margin-bottom: 0.5rem;
  }}
  .hero p {{
    font-size: 1.05rem; color: #CBD5E1; max-width: 800px;
    line-height: 1.6;
  }}

  /* Search */
  .search-wrap {{
    margin-bottom: 2.5rem;
  }}
  .search-input {{
    width: 100%; padding: 0.85rem 1.25rem;
    background: #1F2937; border: 1px solid #334155;
    border-radius: 10px; color: #F1F5F9;
    font-size: 0.95rem; font-family: 'Inter', sans-serif;
    outline: none; transition: all 0.2s;
  }}
  .search-input:focus {{
    border-color: #438ECA; box-shadow: 0 0 0 3px #438ECA22;
  }}
  .search-input::placeholder {{ color: #94A3B8; }}

  /* Filter chips */
  .filter-bar {{
    display: flex; flex-wrap: wrap; gap: 0.5rem;
    margin-bottom: 1.5rem;
  }}
  .filter-chip {{
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.35rem 0.9rem;
    background: #1F2937; border: 1px solid #334155;
    border-radius: 20px;
    font-size: 0.8rem; font-weight: 500; color: #CBD5E1;
    cursor: pointer; transition: all 0.15s;
    user-select: none;
  }}
  .filter-chip:hover {{
    border-color: #4B5563;
  }}
  .filter-chip.active {{
    background: rgba(67,142,202,0.15);
    border-color: #438ECA;
    color: #438ECA;
  }}
  .filter-chip input {{ display: none; }}

  /* Section */
    .section {{
      margin-bottom: 2rem;
    }}
    .section-header {{
      display: flex; align-items: center; gap: 0.75rem;
      margin-bottom: 1.25rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid #334155;
      cursor: pointer;
      user-select: none;
    }}
    .section-header:hover .section-title {{
      color: #F1F5F9;
    }}
    .section-dot {{
      width: 10px; height: 10px; border-radius: 50%;
      flex-shrink: 0;
    }}
    .section-title {{
      font-size: 1.15rem; font-weight: 600; color: #CBD5E1;
      text-transform: uppercase; letter-spacing: 0.06em;
      transition: color 0.15s;
    }}
    .section-count {{
      font-size: 0.8rem; color: #94A3B8;
      margin-left: auto;
      margin-right: 0.5rem;
    }}
    .section-indicator {{
        font-size: 0.65rem; color: #4B5563;
        flex-shrink: 0;
        line-height: 1;
        transition: color 0.15s;
      }}

    /* Collapsible card list */
    .card-list {{
      display: flex; flex-direction: column; gap: 0.75rem;
      overflow: hidden;
      transition: max-height 0.3s ease, opacity 0.2s ease;
      max-height: 2000px;
      opacity: 1;
    }}
    .card-list.collapsed {{
      max-height: 0;
      opacity: 0;
      margin: 0;
      gap: 0;
    }}
  .card {{
    background: #1F2937;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1rem 1.5rem;
    transition: all 0.2s ease;
    display: flex; align-items: center; gap: 1.5rem;
  }}
  .card:hover {{
    border-color: #4B5563;
    transform: translateY(-1px);
    box-shadow: 0 8px 25px -6px rgba(0,0,0,0.3);
  }}
  .card-body {{
    flex: 1; min-width: 0;
  }}
  .card-title {{
    font-size: 1rem; font-weight: 600; color: #f1f5f9;
    margin-bottom: 0.25rem;
    line-height: 1.4;
  }}
  .card-desc {{
    font-size: 0.85rem; color: #CBD5E1;
    line-height: 1.5;
  }}
  .card-link {{
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.5rem 1rem;
    background: #438ECA; color: #0F172A;
    border-radius: 8px;
    font-size: 0.8rem; font-weight: 600;
    text-decoration: none; transition: all 0.2s;
    flex-shrink: 0;
  }}
  .card-link:hover {{
    background: #5A9ED4; transform: translateY(-1px);
  }}
  .card-link svg {{
    width: 14px; height: 14px; flex-shrink: 0;
  }}

  /* No results */
  .no-results {{
    text-align: center; padding: 3rem;
    color: #94A3B8; font-size: 0.95rem;
  }}

  /* Stats footer */
  .stats {{
    text-align: center; padding: 2rem 0;
    font-size: 0.78rem; color: #4B5563;
    border-top: 1px solid #334155;
    margin-top: 2rem;
  }}

  @media (max-width: 640px) {{
    .header {{ padding: 0 1rem; }}
    .container {{ padding: 1.5rem 1rem 3rem; }}
    .hero h1 {{ font-size: 1.75rem; }}
    .card {{ flex-direction: column; align-items: stretch; }}
    .card-link {{ align-self: flex-end; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-inner">
    <div class="logo">
      <img src="data:image/png;base64,{LOGO_B64}" alt="Casago" class="logo-img">
    </div>
    <div class="header-nav">
      <a href="/" class="nav-btn active">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
        Bookmarks
      </a>
      <a href="/dashboard" class="nav-btn">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        Dashboard
      </a>
    </div>
    <div class="header-actions">
      <span class="user-email" id="userEmail">{user_email}</span>
      <a href="/logout" class="btn-logout">Sign out</a>
    </div>
  </div>
</div>

<div class="container">
  <div class="hero">
    <h1>STR Bookmarks</h1>
    <p>Quick-access directory of tools, docs, and resources across every department.</p>
  </div>

  <div class="search-wrap">
    <input class="search-input" id="searchInput" type="text" placeholder="Search bookmarks by title, section, or description…" autocomplete="off">
  </div>

  <div class="filter-bar" id="filterBar"></div>

  <div id="content"><div class="no-results">Loading bookmarks…</div></div>

  <div class="stats" id="stats"></div>
</div>

<script>
const SECTION_COLORS = {{
  "Revenue": "#22c55e",
  "Openings": "#3b82f6",
  "Market Ops": "#a855f7",
  "Guest Experience": "#f97316",
  "Owner Success": "#06b6d4"
}};

const DEFAULT_COLOR = "#CBD5E1";
const SEARCH_KEY = 'str_search';
const FILTER_KEY = 'str_filters';
const COLLAPSE_KEY = 'str_collapsed';

let allSections = [];
let activeFilters = new Set();
let currentQuery = '';

// Load bookmarks
async function loadBookmarks() {{
  try {{
    const resp = await fetch('/api/bookmarks');
    if (resp.status === 401) {{ window.location.href = '/'; return; }}
    const data = await resp.json();
    allSections = data.sections || [];
    initFilters();
    render();
    setupSearch();
  }} catch(e) {{
    document.getElementById('content').innerHTML = '<div class="no-results">Failed to load bookmarks. Please try again.</div>';
  }}
}}

// Initialize filters from session storage or all on
function initFilters() {{
  const saved = sessionStorage.getItem(FILTER_KEY);
  if (saved) {{
    try {{
      const arr = JSON.parse(saved);
      activeFilters = new Set(arr);
      // Prune stale sections
      const valid = new Set(allSections.map(s => s.section));
      for (const f of activeFilters) {{
        if (!valid.has(f)) activeFilters.delete(f);
      }}
    }} catch {{}}
  }}
  if (activeFilters.size === 0) {{
    activeFilters = new Set(allSections.map(s => s.section));
  }}
  renderFilters();
}}

function renderFilters() {{
  const bar = document.getElementById('filterBar');
  bar.innerHTML = '';
  for (const sec of allSections) {{
    const name = sec.section;
    const color = SECTION_COLORS[name] || DEFAULT_COLOR;
    const active = activeFilters.has(name);
    const chip = document.createElement('label');
    chip.className = 'filter-chip' + (active ? ' active' : '');
    chip.innerHTML = `<input type="checkbox" ${{active ? 'checked' : ''}}><span class="section-dot" style="width:8px;height:8px;background:${{color}};border-radius:50%;display:inline-block"></span> ${{name}}`;
    chip.addEventListener('click', (e) => {{
      if (e.target.tagName === 'INPUT') return;
      const cb = chip.querySelector('input');
      cb.checked = !cb.checked;
      toggleFilter(name, cb.checked);
    }});
    chip.querySelector('input').addEventListener('change', (e) => {{
      toggleFilter(name, e.target.checked);
    }});
    bar.appendChild(chip);
  }}
}}

function toggleFilter(name, on) {{
  if (on) activeFilters.add(name);
  else activeFilters.delete(name);
  sessionStorage.setItem(FILTER_KEY, JSON.stringify([...activeFilters]));
  renderFilters();
  render();
}}

function getCollapsedKey(name) {{
  return COLLAPSE_KEY + ':' + name;
}}

function render() {{
  const container = document.getElementById('content');
  const q = currentQuery.toLowerCase().trim();
  let totalItems = 0;
  let anyVisible = false;

  if (!allSections || allSections.length === 0) {{
    container.innerHTML = '<div class="no-results">No bookmarks found.</div>';
    document.getElementById('stats').textContent = '';
    return;
  }}

  let html = '';

  for (const sec of allSections) {{
    if (!activeFilters.has(sec.section)) continue;

    let items = sec.items;
    if (q) {{
      items = items.filter(item =>
        item.title.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        sec.section.toLowerCase().includes(q) ||
        item.owner.toLowerCase().includes(q)
      );
    }}
    if (items.length === 0) continue;

    anyVisible = true;
    totalItems += items.length;
    const color = SECTION_COLORS[sec.section] || DEFAULT_COLOR;
    const collapsed = sessionStorage.getItem(getCollapsedKey(sec.section)) === '1';

        html += `<div class="section">
                  <div class="section-header" data-section="${{sec.section}}">
                    <span class="section-indicator" style="color:${{color}}">${{collapsed ? '▶' : '▼'}}</span>
                    <div class="section-title">${{sec.section}}</div>
                    <div class="section-count">${{items.length}} bookmark${{items.length !== 1 ? 's' : ''}}</div>
                  </div>
              <div class="card-list ${{collapsed ? 'collapsed' : ''}}">`;

    for (const item of items) {{
      const url = item.link.toLowerCase();
            const icon = url.includes('spreadsheet') ? '📊'
              : url.includes('sheets.google.com') ? '📊'
              : url.includes('docs.google.com') ? '📄'
              : url.includes('drive.google.com') ? '📁'
              : url.includes('render.com') ? '⚡'
              : '🔗';
      html += `<div class="card">
        <div class="card-body">
          <div class="card-title">${{icon}} ${{item.title}}</div>
          <div class="card-desc">${{item.description || 'No description'}}</div>
        </div>
        <a href="${{item.link}}" target="_blank" rel="noopener noreferrer" class="card-link">
          Open
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </a>
      </div>`;
    }}

    html += `</div></div>`;
  }}

  container.innerHTML = html || '<div class="no-results">No bookmarks match your current view.</div>';

  // Attach collapse handlers
    container.querySelectorAll('.section-header').forEach(header => {{
      header.addEventListener('click', () => {{
        const name = header.dataset.section;
        const list = header.nextElementSibling;
        const indicator = header.querySelector('.section-indicator');
        const was = sessionStorage.getItem(getCollapsedKey(name));
        if (was === '1') {{
          sessionStorage.removeItem(getCollapsedKey(name));
          list.classList.remove('collapsed');
          indicator.textContent = '▼';
        }} else {{
          sessionStorage.setItem(getCollapsedKey(name), '1');
          list.classList.add('collapsed');
          indicator.textContent = '▶';
        }}
      }});
    }});

  const qtext = q ? ` (filtered to ${{totalItems}})` : '';
  document.getElementById('stats').textContent =
    `${{totalItems}} bookmark${{totalItems !== 1 ? 's' : ''}} across ${{[...activeFilters].filter(f => allSections.some(s => s.section === f)).length}} departments${{qtext}}`;
}}

function setupSearch() {{
  const input = document.getElementById('searchInput');
  const saved = sessionStorage.getItem(SEARCH_KEY);
  if (saved) {{
    input.value = saved;
    currentQuery = saved;
  }}
  let debounceTimer;
  input.addEventListener('input', () => {{
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {{
      currentQuery = input.value;
      sessionStorage.setItem(SEARCH_KEY, currentQuery);
      render();
    }}, 200);
  }});
}}

loadBookmarks();
</script>
</body>
</html>"""

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>STR Bookmarks</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0F172A; color: #F1F5F9;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; margin: 0; padding: 1rem;
  }
  .login-card {
    text-align: center; max-width: 420px; width: 100%;
    background: #1F2937; border: 1px solid #334155;
    border-radius: 16px; padding: 3rem 2.5rem;
  }
  .login-logo {
    max-width: 200px; margin: 0 auto 1.5rem;
  }
  h1 {
    font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em;
    color: #F1F5F9; margin-bottom: 0.5rem;
  }
  p {
    color: #CBD5E1; margin-bottom: 2rem; font-size: 0.9rem; line-height: 1.5;
  }
  .btn-google {
    display: inline-flex; align-items: center; gap: 0.75rem;
    padding: 0.85rem 2rem; background: #438ECA; color: #0F172A;
    border: 0; border-radius: 10px; font-weight: 600;
    font-size: 0.95rem; cursor: pointer; text-decoration: none;
    transition: all 0.2s;
  }
  .btn-google:hover {
    background: #5A9ED4; transform: translateY(-1px);
    box-shadow: 0 8px 25px -6px rgba(67,142,202,0.3);
  }
  .btn-google svg { width: 20px; height: 20px; }
  .domain-hint {
    margin-top: 1.25rem; font-size: 0.78rem; color: #CBD5E1;
  }
</style>
</head>
<body>
<div class="login-card">
  <img src="data:image/png;base64,_LOGO_PLACEHOLDER_" alt="Casago" class="login-logo">
  <h1>STR Bookmarks</h1>
  <p>Internal resources &amp; quick-access tools.<br>Sign in with your work email to continue.</p>
  <a href="/login" class="btn-google">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#0F172A" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#0F172A" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#0F172A" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#0F172A" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
    Sign in with Google
  </a>
  <div class="domain-hint">@roofstock.com email required</div>
</div>
</body>
</html>""".replace("_LOGO_PLACEHOLDER_", LOGO_B64)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
