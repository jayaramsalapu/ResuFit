from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask import make_response
import sqlite3
from flask_bcrypt import Bcrypt
from google_auth_oauthlib.flow import Flow
import requests
import os
import re
from dotenv import load_dotenv
import random
from werkzeug.utils import secure_filename
from docx import Document
from groq_api import analyze_resume_with_groq, analyze_jd_with_groq ,  optimize_text_with_groq, tailor_resume_with_groq, analyze_keywords_with_groq, parse_resume_to_json_with_groq
from document_extractor import extract_document_text, is_good_text, get_tesseract_status
from datetime import timedelta
load_dotenv()


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

bcrypt = Bcrypt(app)

otp_storage = {}
# Allow HTTP only in development
if os.getenv("FLASK_ENV") == "development":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Google OAuth config (from .env)
GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "auth_uri":"https://accounts.google.com/o/oauth2/auth",
        "token_uri":"https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")]
    }
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# ---------------- DB ---------------- #

def get_db():
    db_path = os.path.join(BASE_DIR, 'database.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def create_table():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stats(
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def increment_stat(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM stats WHERE key = ?", (key,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO stats (key, value) VALUES (?, 1)", (key,))
    else:
        conn.execute("UPDATE stats SET value = value + 1 WHERE key = ?", (key,))
    conn.commit()
    conn.close()

def get_stats():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM stats").fetchall()
    stats = {row['key']: row['value'] for row in rows}
    
    users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    
    baseline_analyzed = 1420
    baseline_built = 950
    baseline_downloaded = 780
    
    return {
        'users_count': users_count,
        'resumes_analyzed': baseline_analyzed + stats.get('resumes_analyzed', 0),
        'resumes_built': baseline_built + stats.get('resumes_built', 0),
        'resumes_downloaded': baseline_downloaded + stats.get('resumes_downloaded', 0)
    }

def extract_text(filepath):
    """
    Extract text from a resume document (PDF, DOCX, TXT) using the robust
    multi-layered extraction pipeline (layout-aware PyMuPDF -> PyPDF -> OCR).
    """
    extracted_text, metadata = extract_document_text(filepath)
    app.logger.info(f"Extracted document '{os.path.basename(filepath)}': length={len(extracted_text)}, meta={metadata}")
    return extracted_text

# ---------------- ROUTES ---------------- #

@app.route('/')
def index():
    stats = get_stats()
    return render_template('index.html', stats=stats)


from urllib.parse import urlparse, urljoin

from flask import has_request_context

def is_safe_next_url(target):
    """
    Validate that target is a safe internal URL path to prevent open redirects to external domains.
    """
    if not target or not isinstance(target, str):
        return False
    target = target.strip()
    if not target.startswith('/'):
        return False
    if target.startswith('//') or target.startswith('\\\\') or target.startswith('/\\') or target.startswith('/%5C'):
        return False
    if '://' in target or '\\' in target:
        return False
    if any(ord(c) < 32 or ord(c) == 127 for c in target):
        return False
    if has_request_context():
        ref_url = urlparse(request.host_url)
        test_url = urlparse(urljoin(request.host_url, target))
        return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
    return True


# ---------- REGISTER ---------- #
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        raw_next = request.args.get('next') or session.pop('next_url', None)
        target = raw_next if is_safe_next_url(raw_next) else url_for('dashboard')
        return redirect(target)

    raw_next = request.args.get('next') or request.form.get('next') or session.get('next_url')
    next_url = raw_next if is_safe_next_url(raw_next) else None
    if next_url:
        session['next_url'] = next_url

    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match", next=next_url or '')

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, hashed_password)
            )
            conn.commit()
        except:
            conn.close()
            return render_template('register.html', error="User already exists", next=next_url or '')

        # Log user in directly upon successful registration
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['email'] = user['email']
            session.permanent = True

        target = session.pop('next_url', None) or next_url or url_for('dashboard')
        if not is_safe_next_url(target):
            target = url_for('dashboard')

        return redirect(target)

    return render_template('register.html', next=next_url or '')


# ---------- LOGIN ---------- #
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        raw_next = request.args.get('next') or session.pop('next_url', None)
        target = raw_next if is_safe_next_url(raw_next) else url_for('dashboard')
        return redirect(target)

    raw_next = request.args.get('next') or request.form.get('next') or session.get('next_url')
    next_url = raw_next if is_safe_next_url(raw_next) else None
    if next_url:
        session['next_url'] = next_url

    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        conn.close()

        if user and user['password'] != 'google_auth' and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['email'] = user['email']
            session.permanent = True

            target = session.pop('next_url', None) or next_url or url_for('dashboard')
            if not is_safe_next_url(target):
                target = url_for('dashboard')
            return redirect(target)

        return render_template('login.html', error="Invalid email or password", next=next_url or '')

    return render_template('login.html', next=next_url or '')


# ---------- GOOGLE LOGIN ---------- #
@app.route("/google/login")
def google_login():
    raw_next = request.args.get('next') or session.get('next_url')
    if is_safe_next_url(raw_next):
        session['next_url'] = raw_next

    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ],
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI") 
    )

    authorization_url, state = flow.authorization_url()
    session["state"] = state
    session["code_verifier"] = flow.code_verifier
    return redirect(authorization_url)


# ---------- GOOGLE CALLBACK ---------- #
@app.route("/google/callback")
def google_callback():

    # CSRF protection
    if request.args.get("state") != session.get("state"):
        return "State mismatch", 400

    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ],
        state=session["state"],
        redirect_uri=os.getenv("GOOGLE_REDIRECT_URI") 
    )
    flow.code_verifier = session["code_verifier"]
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials

    # Get user info
    response = requests.get(
        "https://www.googleapis.com/oauth2/v1/userinfo",
        params={"access_token": credentials.token}
    )

    if response.status_code != 200:
        return "Failed to fetch user info", 400

    user_info = response.json()
    email = user_info["email"]

    # Check if user exists
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if not user:
        conn.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, "google_auth")
        )
        conn.commit()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

    conn.close()

    # Login user
    session["user_id"] = user["id"]
    session["email"] = user["email"]
    session.permanent = True

    target = session.pop('next_url', None) or url_for("dashboard")
    if not is_safe_next_url(target):
        target = url_for("dashboard")
    return redirect(target)


# ---------- API AUTH ENDPOINTS (FOR MODAL & GATING) ---------- #
@app.route('/api/auth-status')
def api_auth_status():
    return jsonify({
        "authenticated": 'user_id' in session,
        "email": session.get('email', '')
    })

@app.route('/api/pending-action', methods=['GET', 'POST', 'DELETE'])
def api_pending_action():
    if request.method == 'POST':
        data = request.get_json() or {}
        session['pending_action'] = data
        return jsonify({"success": True})
    elif request.method == 'DELETE':
        session.pop('pending_action', None)
        return jsonify({"success": True})
    return jsonify(session.get('pending_action', {}))

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required"}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if user and user['password'] != 'google_auth' and bcrypt.check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        session['email'] = user['email']
        session.permanent = True
        return jsonify({"success": True, "email": user['email']})

    return jsonify({"success": False, "error": "Invalid email or password"}), 401


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password required"}), 400

    if password != confirm_password:
        return jsonify({"success": False, "error": "Passwords do not match"}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed_password))
        conn.commit()
    except Exception:
        conn.close()
        return jsonify({"success": False, "error": "User already exists"}), 400

    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if user:
        session['user_id'] = user['id']
        session['email'] = user['email']
        session.permanent = True

    return jsonify({"success": True, "email": email})


def send_otp_email(to_email, otp):
    api_key = os.getenv("BREVO_API_KEY") or os.getenv("BREVO_SMTP_KEY")
    sender_email = os.getenv("BREVO_EMAIL")

    if not api_key:
        raise Exception("Brevo API key is missing. Please set BREVO_API_KEY in your environment.")
    if not api_key.startswith("xkeysib-"):
        raise Exception("Invalid API key format. Brevo v3 API keys must start with 'xkeysib-'.")

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key
    }
    payload = {
        "sender": {"name": "ResuFit", "email": sender_email},
        "to": [{"email": to_email}],
        "subject": "Your OTP for Password Reset",
        "htmlContent": f"<html><body><p>Your OTP for password reset is: <strong>{otp}</strong></p></body></html>"
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code in [200, 201, 202]:
            return True
        else:
            raise Exception(f"Brevo API returned status code {response.status_code}: {response.text}")
    except Exception as e:
        raise Exception(f"Brevo API error: {str(e)}")


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        step = request.form.get('step')
        email = request.form.get('email')

       
        if step == "1":
            conn = get_db()
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
            conn.close()

            if not user:
                return render_template('forgot_password.html', step=1, error="Email not found")

            otp = str(random.randint(1000, 9999))
            otp_storage[email] = otp

            try:
                send_otp_email(email, otp)
            except Exception as e:
                return render_template('forgot_password.html', step=1, error=f"Failed to send email: {str(e)}")

            return render_template('forgot_password.html', step=2, email=email)

       
        elif step == "2":
            user_otp = request.form.get('otp')

            if otp_storage.get(email) == user_otp:
                return render_template('forgot_password.html', step=3, email=email)
            else:
                return render_template('forgot_password.html', step=2, email=email, error="Invalid OTP")

 
        elif step == "3":
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if password != confirm_password:
                return render_template('forgot_password.html', step=3, email=email, error="Passwords do not match")

            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

            conn = get_db()
            conn.execute(
                "UPDATE users SET password = ? WHERE email = ?",
                (hashed_password, email)
            )
            conn.commit()
            conn.close()

            otp_storage.pop(email, None)

            return redirect('/login')

    return render_template('forgot_password.html', step=1)



@app.route('/dashboard')
def dashboard():
    email = session.get('email', '')
    name = re.sub(r'\d+', '', email.split('@')[0]) if email else 'Guest'
    return render_template('dashboard.html', email=email, name=name)


@app.route('/check-resume')
def check_resume():
    email = session.get('email', '')
    name = re.sub(r'\d+', '', email.split('@')[0]) if email else 'Guest'
    return render_template('check_resume.html', name=name)


@app.route('/analyze_resume', methods=['POST'])
def analyze_resume():

    file = request.files.get('resume')

    if not file or file.filename == '':
        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "No file selected"}), 400
        return "No file selected", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        file.save(filepath)
        resume_text = extract_text(filepath)
    except Exception as e:
        app.logger.error(f"File upload/saving failed for {filename}: {e}")
        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Could not process uploaded file."}), 400
        return "Could not process uploaded file.", 400
    finally:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

    if not resume_text or not is_good_text(resume_text):
        app.logger.warning(f"Text extraction failed or yielded unusable content for {filename}")
        err_msg = "Could not extract readable text from this PDF/DOCX file. Please ensure the file is not password-protected, encrypted, or corrupted."
        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": err_msg}), 400
        return render_template('check_resume.html', name=session.get('email', 'Guest'), error=err_msg), 400

    result = analyze_resume_with_groq(resume_text)
    
    app.logger.info(
        "Resume AI result keys: %s",
        list(result.keys()) if isinstance(result, dict) else type(result)
    )

    if isinstance(result, dict):
        p_info = result.get("personal_info") or {}
        analysis = result.get("analysis") or {}
        app.logger.info(
            "Resume AI sections: name='%s', personal_info=%s summary=%s skills=%d experience=%d projects=%d grammar=%d improvements=%d",
            p_info.get("name") if isinstance(p_info, dict) else "",
            bool(result.get("personal_info")),
            bool(result.get("summary")),
            len(result.get("skills", [])) if isinstance(result.get("skills"), list) else 0,
            len(result.get("experience", [])) if isinstance(result.get("experience"), list) else 0,
            len(result.get("projects", [])) if isinstance(result.get("projects"), list) else 0,
            len(analysis.get("grammar_and_spelling_mistakes", [])) if isinstance(analysis, dict) and isinstance(analysis.get("grammar_and_spelling_mistakes"), list) else 0,
            len(analysis.get("content_improvements", [])) if isinstance(analysis, dict) and isinstance(analysis.get("content_improvements"), list) else 0
        )

        if result.get("error") and not result.get("personal_info", {}).get("name"):
            app.logger.error("AI Analysis failed: %s", result.get("error"))
            err_msg = f"AI analysis error: {result.get('error')}"
            if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": err_msg}), 400
            return render_template('check_resume.html', name=session.get('email', 'Guest'), error=err_msg), 400

    email = session.get('email', '')
    name = re.sub(r'\d+', '', email.split('@')[0]) if email else 'Guest'

    increment_stat('resumes_analyzed')

    if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(result)

    return render_template('check_resume.html', name=name, result=result)

@app.route('/jd_analysis')
def jd_analysis_page():
    email = session.get('email', '')
    name = re.sub(r'\d+', '', email.split('@')[0]) if email else 'Guest'
    return render_template('jd_analysis.html', name=name)


@app.route('/analyze_jd', methods=['POST'])
def analyze_jd():
    file = request.files.get('resume')
    jd_text = request.form.get('jd_text', '')

    if not file or file.filename == '':
        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "No file selected"}), 400
        return "No file selected", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        file.save(filepath)
        resume_text = extract_text(filepath)
    except Exception as e:
        app.logger.error(f"File upload/saving failed for {filename}: {e}")
        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Could not process uploaded file."}), 400
        return "Could not process uploaded file.", 400
    finally:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

    if not resume_text or not is_good_text(resume_text):
        app.logger.warning(f"Text extraction failed or yielded unusable content for {filename}")
        err_msg = "Could not extract readable text from this PDF/DOCX file. Please ensure the file is not password-protected, encrypted, or corrupted."
        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": err_msg}), 400
        return render_template('jd_analysis.html', name=session.get('email', 'Guest'), error=err_msg, jd_text=jd_text), 400

    result = analyze_jd_with_groq(resume_text, jd_text)
    
    email = session.get('email', '')
    name = re.sub(r'\d+', '', email.split('@')[0]) if email else 'Guest'

    increment_stat('resumes_analyzed')

    if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(result)

    return render_template('jd_analysis.html', name=name, result=result, jd_text=jd_text)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')



@app.route('/builder')
def builder():
    increment_stat('resumes_built')
    return render_template('builder.html')

@app.route('/track_download', methods=['POST'])
def track_download():
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "Login required"}), 401
    increment_stat('resumes_downloaded')
    return jsonify({"success": True})

# ==========================
# AI POLISH
# ==========================

@app.route('/optimize-text', methods=['POST'])
def optimize_text():

    try:
        data = request.get_json()

        text = data.get('text', '')
        text_type = data.get('type', 'general')

        if not text.strip():
            return jsonify({
                "error": "No text provided"
            }), 400

        optimized = optimize_text_with_groq(
            text,
            text_type
        )

        return jsonify({
            "optimized": optimized
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# ==========================
# RESUME TAILORING
# ==========================

@app.route('/tailor-resume', methods=['POST'])
def tailor_resume():

    try:
        data = request.get_json()

        resume_data = data.get('resumeData', {})
        job_desc = data.get('jobdesc', '')

        if not job_desc:
            return jsonify({
                "error": "Job description missing"
            }), 400

        tailored = tailor_resume_with_groq(
            resume_data,
            job_desc
        )

        # Fix Experience descriptions
        for exp in tailored.get("experience", []):

            desc = exp.get("description")

            if isinstance(desc, list):

                exp["description"] = "\n".join(
                    f"• {str(item).strip().lstrip('•*- ')}"
                    for item in desc
                    if str(item).strip()
                )

        # Fix Project descriptions
        for proj in tailored.get("projects", []):

            desc = proj.get("description")

            if isinstance(desc, list):

                proj["description"] = "\n".join(
                    f"• {str(item).strip().lstrip('•*- ')}"
                    for item in desc
                    if str(item).strip()
                )



        return jsonify({
            "success": True,
            "tailored": tailored
        })

    except Exception as e:

        import traceback
        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==========================
# KEYWORD ANALYZER
# ==========================

@app.route('/analyze-keywords', methods=['POST'])
def analyze_keywords():

    try:
        data = request.get_json()

        resume_data = data.get('resumeData', {})
        job_desc = data.get('jobdesc', '')

        result = analyze_keywords_with_groq(
            resume_data,
            job_desc
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.route('/import_resume', methods=['POST'])
def import_resume():
    file = request.files.get('resume')
    if not file or file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        file.save(filepath)
        resume_text = extract_text(filepath)
        if not resume_text or not is_good_text(resume_text):
            return jsonify({"error": "Could not extract readable text from this PDF/DOCX file. Please check if the file is encrypted or corrupted."}), 400

        parsed_data = parse_resume_to_json_with_groq(resume_text)
        return jsonify(parsed_data)
    except Exception as e:
        app.logger.error(f"Error in import_resume: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass


# ==========================
# PWA SUPPORT ROUTES
# ==========================

@app.route('/manifest.json')
def serve_manifest():
    response = make_response(app.send_static_file('manifest.json'))
    response.headers['Content-Type'] = 'application/json'
    return response

@app.route('/service-worker.js')
def serve_service_worker():
    response = make_response(app.send_static_file('service-worker.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.route('/offline.html')
def serve_offline():
    return render_template('offline.html')

# Ensure database tables exist on startup
create_table()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)