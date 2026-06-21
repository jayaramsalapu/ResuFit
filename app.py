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
from PyPDF2 import PdfReader
from docx import Document
from groq_api import analyze_resume_with_groq, analyze_jd_with_groq ,  optimize_text_with_groq, tailor_resume_with_groq, analyze_keywords_with_groq
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
    conn.commit()
    conn.close()

def extract_text(filepath):
    text = ""

    if filepath.endswith(".pdf"):
        reader = PdfReader(filepath)
        for page in reader.pages:
            text += page.extract_text() or ""

    elif filepath.endswith(".docx"):
        doc = Document(filepath)
        for para in doc.paragraphs:
            text += para.text + "\n"

    return text

# ---------------- ROUTES ---------------- #

@app.route('/')
def index():
    return render_template('index.html')


# ---------- REGISTER ---------- #
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect('/dashboard')

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match")

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (email, password) VALUES (?, ?)",
                (email, hashed_password)
            )
            conn.commit()
        except:
            return render_template('register.html', error="User already exists")

        conn.close()

        return redirect('/login')

    return render_template('register.html')


# ---------- LOGIN ---------- #
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect('/dashboard')

    if request.method == 'POST':
        email = request.form['email']
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
            return redirect(url_for('dashboard'))

        return render_template('login.html', error="Invalid email or password")

    return render_template('login.html')


# ---------- GOOGLE LOGIN ---------- #
@app.route("/google/login")
def google_login():

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

    return redirect(url_for("dashboard"))


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
    if 'user_id' not in session:
        return redirect('/login')
    
    email = session['email']

    name = re.sub(r'\d+', '', email.split('@')[0])

    
    return render_template('dashboard.html', email=session['email'],name=name)


@app.route('/check-resume')
def check_resume():
    if 'user_id' not in session:
        return redirect('/login')

    email = session['email']
    name = re.sub(r'\d+', '', email.split('@')[0])

    return render_template('check_resume.html', name=name)


@app.route('/analyze_resume', methods=['POST'])
def analyze_resume():

    file = request.files.get('resume')

    if not file or file.filename == '':
        return "No file selected"

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    resume_text = extract_text(filepath)
    os.remove(filepath)
    result = analyze_resume_with_groq(resume_text)
    
    email = session.get('email', '')
    name = re.sub(r'\d+', '', email.split('@')[0]) if email else 'User'

    if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(result)

    return render_template('check_resume.html', name=name, result=result)

@app.route('/jd_analysis')
def jd_analysis_page():
    if 'user_id' not in session:
        return redirect('/login')

    email = session['email']
    name = re.sub(r'\d+', '', email.split('@')[0])

    return render_template('jd_analysis.html', name=name)


@app.route('/analyze_jd', methods=['POST'])
def analyze_jd():
    if 'user_id' not in session:
        return redirect('/login')

    file = request.files.get('resume')
    jd_text = request.form.get('jd_text', '')

    if not file or file.filename == '':
        return "No file selected"

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    resume_text = extract_text(filepath)
    os.remove(filepath)
    result = analyze_jd_with_groq(resume_text, jd_text)
    
    email = session.get('email', '')
    name = re.sub(r'\d+', '', email.split('@')[0]) if email else 'User'

    if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(result)

    return render_template('jd_analysis.html', name=name, result=result, jd_text=jd_text)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')



@app.route('/builder')
def builder():
    return render_template('builder.html')

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

if __name__ == "__main__":
    create_table()
    app.run(host="0.0.0.0", port=5000, debug=True)