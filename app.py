from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from flask_bcrypt import Bcrypt
from google_auth_oauthlib.flow import Flow
import requests
import os
import re
from dotenv import load_dotenv
from flask_mail import Mail, Message
import random
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from docx import Document
from groq_api import analyze_resume_with_groq, analyze_jd_with_groq
load_dotenv()


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.getenv("EMAIL_PASS")
mail = Mail(app)
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

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# ---------------- DB ---------------- #

def get_db():
    conn = sqlite3.connect('database.db')
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

    return redirect(url_for("dashboard"))


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

            otp = str(random.randint(100000, 999999))
            otp_storage[email] = otp

            msg = Message(
                'Your OTP for Password Reset',
                sender=app.config['MAIL_USERNAME'],
                recipients=[email]
            )
            msg.body = f"Your OTP is: {otp}"
            mail.send(msg)

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
    result = analyze_resume_with_groq(resume_text)
    
    email = session.get('email', '')
    name = re.sub(r'\d+', '', email.split('@')[0]) if email else 'User'

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
    result = analyze_jd_with_groq(resume_text, jd_text)
    
    email = session.get('email', '')
    name = re.sub(r'\d+', '', email.split('@')[0]) if email else 'User'

    return render_template('jd_analysis.html', name=name, result=result, jd_text=jd_text)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')



if __name__ == '__main__':
    create_table()
    app.run(debug=True)