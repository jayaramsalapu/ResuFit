import os
import json
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_resume_with_groq(resume_text):
    prompt = f"""
Act as an elite executive recruiter and an advanced, strict AI Applicant Tracking System (ATS).

Analyze the provided resume extremely strictly against the following 15 ATS rules:

1. BASIC INFORMATION: Must have full name, valid email, phone. LinkedIn/GitHub recommended.
2. STRUCTURE AND ORGANIZATION: Clearly defined sections (Summary, Skills, Experience, Projects, Education, Certifications). Content must be logical.
3. FORMATTING RULES: Simple, ATS-friendly. No complex tables. Standard fonts, bullet points preferred.
4. GRAMMAR AND LANGUAGE: ZERO spelling/grammar mistakes. Professional/formal language only (no slang).
5. SKILLS SECTION: Clearly listed. Specific technical skills. Avoid vague soft skills.
6. EXPERIENCE SECTION: Must include role, company, duration. Strong action verbs. Measurable impact. No generic descriptions.
7. PROJECTS SECTION: Title, description, tech used, outcome/purpose.
8. EDUCATION SECTION: Degree, institution, year.
9. CERTIFICATIONS: Only relevant, clearly named.
10. CONTENT QUALITY: Concise, no repetition, no filler.
11. CONSISTENCY: Consistent formatting, tense (past tense preferred), bullet style.
12. ACTION AND IMPACT: Action-oriented sentences, focus on achievements/results.
13. COMPLETENESS: All major sections present. No empty/missing critical details.
14. RED FLAGS: Deduct heavily for missing contact info, missing skills/experience, poor grammar, or confusing structure.

Resume:
{resume_text}

Return EXACTLY AND ONLY this JSON format:
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
    "improvements_to_stand_out": [
      "",
      ""
    ],
    "formatting_and_structure_feedback": ""
  }}
}}

RULES FOR OUTPUT:
1. `ats_score` (0-100) must ruthlessly reflect adherence to the 15 rules.
2. `grammar_and_spelling_mistakes` must extract the exact `bullet_point_with_error` from the resume, and provide a highly professional, ATS-optimized `stylish_correction` to replace it. If absolutely none exist, leave the list empty: [].
3. `improvements_to_stand_out` must provide 3-5 highly specific, actionable, professional critiques based on the 15 rules to elevate the resume. If none, leave empty.
4. If a field is missing, leave it blank or as an empty list as appropriate. DO NOT output any markdown ticks (` ```json `), ONLY the raw braces.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    content = response.choices[0].message.content

    match = re.search(r'\{.*\}', content, re.DOTALL)

    if match:
        try:
            return json.loads(match.group())
        except:
            return {}

    return {}


def analyze_jd_with_groq(resume_text, jd_text):
    prompt = f"""
Act as an advanced ATS (Applicant Tracking System) and professional recruiter.

Your task is to analyze the resume against the given job description and provide a detailed evaluation and improvement suggestions.

JOB DESCRIPTION:
{jd_text}

RESUME:
{resume_text}

Perform the following analysis:

1. Candidate Information Extraction:
* Extract name, email, phone, LinkedIn, GitHub

2. Skills Analysis:
* Extract all skills from the resume
* Compare with required skills in the job description
* Identify:  • Matching skills  • Missing skills  • Irrelevant skills
* Suggest skills to add based on the job description

3. Experience Evaluation:
* Analyze work experience relevance to the job role
* Check if experience descriptions are strong and impact-driven
* Identify weak or vague descriptions
* Rewrite experience points with:  • action verbs  • measurable results  • clearer impact

4. Projects Evaluation:
* Check if projects are relevant to the job role
* Evaluate clarity and technical depth
* Suggest improvements
* Recommend additional project ideas if lacking

5. Education Evaluation:
* Check if education is relevant and clearly presented
* Suggest improvements if needed

6. Certifications:
* Identify certifications listed
* Suggest relevant certifications for the job role if missing

7. Grammar and Language:
* Identify grammar and spelling mistakes
* Rewrite incorrect or weak sentences professionally

8. Resume Structure and Formatting:
* Check if resume follows proper structure: Summary, Skills, Experience, Projects, Education
* Identify missing sections
* Suggest improvements for clarity and readability

9. Overall Match Analysis:
* Provide a match percentage between resume and job description
* Explain why the match is high or low

10. Final Improvements:
* Provide clear, actionable steps to improve the resume for this job role

Return the output STRICTLY in the following JSON format:

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

IMPORTANT RULES:
* Return ONLY valid JSON
* Do NOT include any extra text, explanation, or markdown
* Ensure all fields are present (use empty values if needed)
* Keep output structured and clean
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    content = response.choices[0].message.content

    match = re.search(r'\{.*\}', content, re.DOTALL)

    if match:
        try:
            return json.loads(match.group())
        except:
            return {}

    return {}
