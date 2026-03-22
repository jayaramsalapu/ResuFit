import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ---------------------------
# RESUME ANALYSIS (ATS MODE)
# ---------------------------
def analyze_resume_with_groq(resume_text):
    prompt = f"""
ROLE:
You are an elite executive recruiter and a strict ATS system.

TASK:
Analyze the resume strictly using ATS standards.

PROCESS (internal, do not output):
1. Extract structured resume data
2. Evaluate against ATS rules
3. Identify weaknesses
4. Generate improvements

ATS SCORING GUIDELINE:
- 90–100: Excellent (no issues)
- 70–89: Strong (minor gaps)
- 50–69: Moderate issues
- 30–49: Weak
- <30: Poor

RESUME:
{resume_text}

OUTPUT FORMAT (STRICT JSON ONLY):
{{
  "personal_info": {{
    "name": "",
    "email": "",
    "phone": "",
    "linkedin": "",
    "github": "",
    "portfolio": ""
  }},
  "summary": "",
  "skills": [],
  "experience": [
    {{
      "role": "",
      "company": "",
      "duration": "",
      "description": ""
    }}
  ],
  "projects": [
    {{
      "title": "",
      "description": "",
      "technologies": []
    }}
  ],
  "education": [
    {{
      "degree": "",
      "institution": "",
      "year": ""
    }}
  ],
  "certifications": [],
  "analysis": {{
    "ats_score": 0,
    "grammar_and_spelling_mistakes": [
      {{
        "mistake": "",
        "correction": "",
        "explanation": ""
      }}
    ],
    "improvements_to_stand_out": [],
    "formatting_and_structure_feedback": ""
  }}
}}

STRICT OUTPUT RULES:
- Output MUST be valid JSON (parsable with json.loads)
- Do NOT include markdown or backticks
- Do NOT include comments or extra text
- Do NOT change keys
- If data is missing, use "" or []
- grammar_and_spelling_mistakes:
  - Extract exact sentence
  - Provide corrected version
  - Give short explanation
- Experience descriptions MUST be professional and clear
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except:
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group())
            except:
                return {}
    return {}


# ---------------------------
# JD MATCH ANALYSIS
# ---------------------------
def analyze_jd_with_groq(resume_text, jd_text):
    prompt = f"""
ROLE:
You are an advanced ATS system and professional recruiter.

TASK:
Compare the resume against the job description and provide a strict evaluation.

PROCESS (internal, do not output):
1. Extract candidate details
2. Extract resume skills
3. Extract required JD skills
4. Compare and classify skills
5. Evaluate experience relevance
6. Evaluate projects
7. Identify gaps
8. Generate improvements

MATCH SCORING WEIGHT:
- Skills match: 40%
- Experience relevance: 30%
- Projects relevance: 15%
- Education + certifications: 15%

JOB DESCRIPTION:
{jd_text}

RESUME:
{resume_text}

OUTPUT FORMAT (STRICT JSON ONLY):
{{
"candidate": {{
"name": "",
"email": "",
"phone": "",
"linkedin": "",
"github": ""
}},
"skills": {{
"matched": [],
"missing": [],
"irrelevant": [],
"suggestions": []
}},
"experience": {{
"relevance": "",
"issues": [],
"improved_points": []
}},
"projects": {{
"relevance": "",
"issues": [],
"suggestions": []
}},
"education": {{
"details": "",
"suggestions": []
}},
"certifications": {{
"existing": [],
"recommended": []
}},
"grammar": {{
"mistakes": [],
"improvements": []
}},
"structure": {{
"issues": [],
"suggestions": []
}},
"match_analysis": {{
"percentage": "",
"reason": ""
}},
"final_suggestions": []
}}

STRICT OUTPUT RULES:
- Output MUST be valid JSON
- No markdown, no explanations
- Do NOT change keys
- All fields must exist

QUALITY RULES:
- Skills:
  - Extract required skills from JD FIRST
  - Then compare
- Experience improved_points:
  - Start with strong action verb
  - Include measurable impact (numbers, %, scale)
  - 1–2 lines max
- Grammar:
  - Show incorrect sentence + corrected version
- match_analysis:
  - percentage must reflect weighted scoring
  - reason must clearly justify score
- final_suggestions:
  - Provide 5–8 high-impact improvements
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except:
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group())
            except:
                return {}
    return {}