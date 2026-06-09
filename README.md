# 📝 ResuFit - AI Resume Builder & ATS Optimization Engine

ResuFit is a premium, AI-powered resume intelligence platform designed to help job seekers build, analyze, tailor, and optimize their resumes to pass Applicant Tracking Systems (ATS) and impress hiring managers.

By leveraging advanced large language models (LLMs) via the Groq API, ResuFit provides instant, deep recruiter-grade feedback, grammar checks, keyword matching, and automated job tailoring.

---

## 🚀 Key Features & How It Works (Step-by-Step)

### Step 1: Build Your Resume

Create a clean, recruiter-focused, ATS-friendly resume from scratch or import existing details.

#### ✨ Features

* **Smart Fields:** Enter details for personal information, summaries, skills, work history, projects, and education.
* **AI Polish:** Tap on the **AI Polish** button next to summaries or experience descriptions to automatically optimize phrasing, improve readability, and ensure grammatical perfection.
* **Interactive Design:** Instantly switch templates, preview formatting, and download your polished resume as a high-quality PDF in one click.

> 📌 *Build professional resumes that are optimized for both recruiters and ATS systems.*

---

### Step 2: Check Your Resume (ATS Compatibility)

Get an objective, rigorous review of your existing resume.

#### 🔍 Features

* **File Processing:** Upload your resume in **PDF** or **DOCX** format.
* **ATS Compatibility Scan:** The engine scores your resume based on key ATS criteria, grammar, spelling, formatting issues, and readability.
* **Recruiter Concerns Detection:** Identifies:

  * Missing achievements
  * Weak action verbs
  * Formatting issues
  * Potential recruiter concerns

Provides actionable suggestions to improve your resume quality.

---

### Step 3: Verify with Job Description (JD Match)

Evaluate your resume against specific target roles before applying.

#### 🎯 Features

* **Gap Analysis:** Upload your resume and paste the target Job Description (JD).
* **Weighted Match Score:** Generates a percentage score based on:

| Evaluation Factor          | Weight |
| -------------------------- | ------ |
| Skills Match               | 40%    |
| Experience Relevance       | 30%    |
| Projects Relevance         | 15%    |
| Education & Certifications | 15%    |

* **Keyword Matching:** Displays:

  * Matched keywords
  * Missing keywords
  * Grammar issues
  * Structural recommendations

> 📌 *Know how closely your resume aligns with your target role before you apply.*

---

### Step 4: Job Tailoring

Automatically customize your resume for a specific Job Description.

#### 🤖 Features

* **Keyword Distribution:** Integrates missing JD skills naturally throughout:

  * Summary
  * Experience
  * Projects

* **Quantifiable Impact:** Enhances descriptions using strong action verbs such as:

  * Engineered
  * Optimized
  * Automated
  * Developed
  * Implemented

* **Business Value Focus:** Highlights measurable achievements without introducing inaccurate information.

* **Formatted Output:** Converts experiences and projects into concise, ATS-friendly bullet points.

> 📌 *Increase your chances of passing ATS filters while maintaining authenticity.*

---

## 🛠️ Technology Stack

ResuFit is engineered using a modern, lightweight, and performance-focused architecture.

### Backend

* **Framework:** Python / Flask
* Handles:

  * Authentication
  * Routing
  * Database interactions
  * File uploads

### AI Engine

* **Provider:** Groq Cloud API
* **Models:** `llama-3.3-70b-versatile` and custom configurations

Used for:

* Resume analysis
* ATS scoring
* Keyword detection
* Grammar checks
* Resume optimization
* Job tailoring

### Database

* **SQLite3**
* Secure storage of user accounts and hashed passwords.

### Authentication

Supports:

* Google OAuth 2.0 Sign-In
* Email Registration/Login
* OTP-based password reset using Gmail SMTP

### Document Processing

* **PyPDF2** → PDF extraction
* **python-docx** → DOCX extraction

### Frontend

* HTML5
* CSS3 (Vanilla)
* Vanilla JavaScript (ES6)

Features include:

* Premium dark-themed UI
* Responsive layouts
* CSS animations
* Interactive score indicators

### Production Server

* **Gunicorn**
* Enables robust and concurrent request handling.

---

## 🌐 Hosting & Keep-Alive Strategy

### Hosting Platform

* **Render (Free Tier)**

### Preventing Cold Starts

Render's free-tier services automatically sleep after **15 minutes of inactivity**, causing startup delays of **50+ seconds**.

To prevent this:

* **UptimeRobot** sends an HTTP request every **5 minutes** to keep the application active.

#### Application URL

```text
https://resufit-w511.onrender.com/
```

This ensures:

* Faster response times
* Better user experience
* Reduced downtime perception

---

## 💻 Local Setup & Installation

### 1. Prerequisites

Ensure you have the following installed:

* Python 3.8+

---

### 2. Clone the Repository

```bash
git clone https://github.com/jayaramsalapu/ResuFit.git

cd ResuFit
```

---

### 3. Create a Virtual Environment

#### Windows

```bash
python -m venv env

.\env\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv env

source env/bin/activate
```

---

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 5. Configure Environment Variables

Create a `.env` file in the project root:

```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=your_flask_secret_key

# Groq API Configuration
GROQ_API_KEY=your_groq_api_key_here

# SQLite Database
DATABASE=database.db

# Email / SMTP Configuration
EMAIL_USER=your_gmail_address@gmail.com
EMAIL_PASS=your_gmail_app_password

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_PROJECT_ID=your_google_project_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/google/callback
```

---

### 6. Run the Application

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000/
```

---

## ☁️ Deployment Guide

### Deploying to Render

1. Create a new **Web Service** on Render.
2. Connect your GitHub repository.
3. Configure the following settings:

| Setting       | Value                             |
| ------------- | --------------------------------- |
| Runtime       | Python                            |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app`                |

4. Add all environment variables from your `.env` file under **Environment Variables**.
5. Update the Google callback URL:

```text
https://resufit-w511.onrender.com/google/callback
```

---

## 🔄 Setting Up UptimeRobot Keep-Alive

1. Sign up or log in to UptimeRobot.
2. Click **Add New Monitor**.
3. Select **HTTP(s)** as the monitor type.
4. Enter a monitor name:

```text
ResuFit Keep Warm
```

5. Enter your application URL:

```text
https://resufit-w511.onrender.com/
```

6. Set the monitoring interval to:

```text
Every 5 Minutes
```

7. Click **Create Monitor**.

---

## 🎯 Mission

ResuFit aims to bridge the gap between job seekers and modern recruitment systems by providing intelligent resume optimization tools that improve ATS compatibility while maintaining authenticity and professionalism.

Build smarter. Apply confidently. Get hired faster.

---

**Made with ❤️**
