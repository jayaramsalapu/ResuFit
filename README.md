# 📝 ResuFit - AI Resume Builder & ATS Optimization Engine

<p align="center">
  <b>Build • Analyze • Optimize • Tailor Your Resume with AI</b>
</p>

ResuFit is an **AI-powered Resume Intelligence Platform** that helps job seekers create professional resumes, optimize them for **Applicant Tracking Systems (ATS)**, and tailor them for specific job descriptions using advanced **Large Language Models (LLMs)**.

It provides recruiter-grade resume analysis, ATS scoring, keyword optimization, grammar improvement, and automatic job-specific tailoring to maximize interview opportunities.

---

## 🌐 Live Demo

**Website:** https://resufit-w511.onrender.com/

---

# 🚀 Features

## 📝 AI Resume Builder

Create a professional ATS-friendly resume from scratch.

* Personal Information
* Professional Summary
* Skills
* Work Experience
* Projects
* Education
* Certifications

### ✨ AI Polish

Improve your content instantly using AI:

* Better grammar
* Professional wording
* Strong action verbs
* Improved readability

---

## 📊 ATS Resume Checker

Upload your resume in **PDF** or **DOCX** format and receive a comprehensive ATS analysis.

### Analysis Includes

* Grammar Check
* Spelling Check
* Formatting Issues
* Readability Analysis
* Recruiter Suggestions
* Missing Achievements
* Weak Action Verbs Detection

---

## 🎯 Job Description (JD) Match

Compare your resume with any job description.

### Match Score Based On

* Skills Match (**40%**)
* Experience (**30%**)
* Projects (**15%**)
* Education & Certifications (**15%**)

### Additional Insights

* Matched Keywords
* Missing Keywords
* Resume Gaps
* ATS Recommendations

---

## ⚡ AI Resume Tailoring

Automatically customize your resume according to the target job description.

### AI Optimizations

* Adds missing keywords naturally
* Improves Summary section
* Enhances Experience descriptions
* Optimizes Projects
* Uses strong action verbs
* Generates recruiter-friendly bullet points

Example:

Instead of:

> Worked on web application.

AI transforms it into:

> Engineered and optimized a responsive web application, improving usability and reducing processing time through efficient backend integration.

---

# 🛠️ Technology Stack

| Technology       | Purpose             |
| ---------------- | ------------------- |
| Python           | Backend             |
| Flask            | Web Framework       |
| Groq API         | AI Engine           |
| Llama 3.3 70B    | Resume Intelligence |
| SQLite           | Database            |
| Google OAuth 2.0 | Authentication      |
| Gmail SMTP       | OTP Verification    |
| PyPDF2           | PDF Parsing         |
| python-docx      | DOCX Parsing        |
| HTML5            | Frontend            |
| CSS3             | Styling             |
| JavaScript (ES6) | Interactivity       |
| Gunicorn         | Production Server   |
| Render           | Deployment          |

---

# 📂 Project Structure

```text
ResuFit/
│
├── static/
│   ├── images/
│   ├── videos/
│   └── style.css
│
├── templates/
│   ├── builder.html
│   ├── check_resume.html
│   ├── dashboard.html
│   ├── forgot_password.html
│   ├── index.html
│   ├── jd_analysis.html
│   ├── login.html
│   └── register.html
│
├── uploads/
│
├── app.py
├── groq_api.py
├── database.db
├── requirements.txt
├── Procfile
├── .env
└── .gitignore
```

---

# 💻 Local Installation

## 1. Clone Repository

```bash
git clone https://github.com/jayaramsalapu/ResuFit.git

cd ResuFit
```

---

## 2. Create Virtual Environment

### Windows

```bash
python -m venv env

.\env\Scripts\activate
```

### macOS/Linux

```bash
python3 -m venv env

source env/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Create a `.env` file.

```env
FLASK_APP=app.py
FLASK_ENV=development

SECRET_KEY=your_secret_key

GROQ_API_KEY=your_groq_api_key

DATABASE=database.db

EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_password

GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_PROJECT_ID=your_project_id
GOOGLE_REDIRECT_URI=http://127.0.0.1:5000/google/callback
```

---

## 5. Run Application

```bash
python app.py
```

Open:

```
http://127.0.0.1:5000
```

---

# ☁️ Deployment (Render)

## Build Command

```bash
pip install -r requirements.txt
```

## Start Command

```bash
gunicorn app:app
```

Configure all environment variables in the Render dashboard.

For production:

```
GOOGLE_REDIRECT_URI=https://resufit-w511.onrender.com/google/callback
```

---

# 🔥 Keep-Alive Strategy

Since Render's free tier may sleep after inactivity, UptimeRobot can periodically ping the application to reduce cold starts.

Configuration:

* Monitor Type: HTTP(s)
* URL:
  https://resufit-w511.onrender.com/
* Interval:
  Every **5 minutes**

---

# 🎯 Highlights

* ✅ AI Resume Builder
* ✅ ATS Resume Checker
* ✅ Job Description Matching
* ✅ AI Resume Tailoring
* ✅ Google OAuth Login
* ✅ OTP Authentication
* ✅ PDF Export
* ✅ Responsive UI
* ✅ Recruiter-Oriented Feedback

---


