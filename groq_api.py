import os
import json
import re
import ast
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("groq_api")

try:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
except Exception:
    client = None


def repair_truncated_json(json_str: str) -> str:
    """
    Attempt to repair a truncated JSON string by closing unclosed strings,
    arrays, and objects if the LLM output was cut off mid-response.
    """
    if not json_str:
        return json_str

    s = json_str.strip()

    # 1. Close unclosed string if output ended mid-string
    in_string = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and in_string:
            i += 2
            continue
        if c == '"':
            in_string = not in_string
        i += 1

    if in_string:
        s += '"'

    # 2. Clean trailing comma or unclosed key-value pair
    s = re.sub(r',\s*$', '', s)
    s = re.sub(r':\s*$', ': ""', s)
    s = re.sub(r',\s*([\}\]])', r'\1', s)

    # 3. Track open brackets '{' and '['
    stack = []
    in_str = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and in_str:
            i += 2
            continue
        if c == '"':
            in_str = not in_str
        elif not in_str:
            if c in '{[':
                stack.append(c)
            elif c in '}]':
                if stack:
                    if (c == '}' and stack[-1] == '{') or (c == ']' and stack[-1] == '['):
                        stack.pop()
        i += 1

    # Close remaining open brackets in reverse order
    while stack:
        b = stack.pop()
        if b == '{':
            s += '}'
        elif b == '[':
            s += ']'

    return s


def _clean_and_parse_json(content: str, fallback_dict: dict = None) -> dict:
    """
    Robust JSON parser for Groq AI responses.
    Handles raw JSON, markdown code blocks, outermost JSON object extraction,
    and truncated JSON auto-repair.
    """
    if not content or not isinstance(content, str):
        logger.error("Groq returned empty or invalid response content")
        return fallback_dict or {"error": "AI returned empty response"}

    logger.info("Groq response received: type=%s length=%d", type(content).__name__, len(content))

    # 1. Try direct JSON parsing
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            logger.info("Groq response parsed successfully via direct json.loads()")
            return data
    except Exception:
        pass

    # 2. Try removing markdown code blocks (e.g. ```json ... ```)
    cleaned = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            logger.info("Groq response parsed successfully after removing markdown code blocks")
            return data
    except Exception:
        pass

    # 3. Try extracting outermost JSON object using regex
    match = re.search(r'\{[\s\S]*\}', content)
    if match:
        extracted = match.group(0)
        try:
            data = json.loads(extracted)
            if isinstance(data, dict):
                logger.info("Groq response parsed successfully via regex object extraction")
                return data
        except Exception:
            # 4. Clean stray markdown syntax or trailing commas within extracted block
            extracted_cleaned = re.sub(r'```(?:json)?', '', extracted)
            extracted_cleaned = re.sub(r',\s*([\}\]])', r'\1', extracted_cleaned)
            try:
                data = json.loads(extracted_cleaned)
                if isinstance(data, dict):
                    logger.info("Groq response parsed successfully after cleaning inner markdown/syntax")
                    return data
            except Exception:
                pass

    # 5. Try repairing truncated JSON if the response was cut off mid-sentence
    try:
        repaired = repair_truncated_json(content)
        data = json.loads(repaired)
        if isinstance(data, dict):
            logger.info("Groq response parsed successfully after JSON truncation repair")
            return data
    except Exception as e:
        logger.debug(f"JSON repair attempt failed: {e}")

    logger.error("Groq JSON parse failed. First 1000 chars: %s", content[:1000])
    if fallback_dict is not None:
        fallback = dict(fallback_dict)
        fallback["error"] = "AI response could not be parsed as valid JSON"
        return fallback

    return {"error": "AI response could not be parsed as valid JSON"}


# ---------------------------
# RESUME ANALYSIS (ATS MODE)
# ---------------------------
def analyze_resume_with_groq(resume_text):
    prompt = f"""
ROLE:
You are an elite executive recruiter, hiring manager, HR reviewer, resume writer, English language editor, and resume optimization expert.

TASK:
Perform a COMPLETE resume review.

Review the resume from:
1. Recruiter perspective
2. Hiring manager perspective
3. Resume writer perspective
4. Grammar editor perspective
5. ATS compatibility perspective

PROCESS (internal, do not output):
1. Extract structured resume data.
2. Review every section line-by-line.
3. Identify ALL grammar, spelling, wording, and formatting issues.
4. Identify weak resume content.
5. Identify missing achievements and missing impact.
6. Improve weak descriptions.
7. Return ALL issues found.

IMPORTANT:
* Review every sentence.
* Review every bullet point.
* Review every section.
* Do NOT stop after finding a few issues.
* Return every genuine issue found.
* If no issue exists, do not invent one.
* Be extremely strict.

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
    "grammar_and_spelling_mistakes": [
      {{
        "mistake": "",
        "correction": "",
        "explanation": ""
      }}
    ],
    "content_improvements": [
      {{
        "original_text": "",
        "improved_text": "",
        "reason": ""
      }}
    ],
    "improvements_to_stand_out": [],
    "formatting_and_structure_feedback": "",
    "missing_information": [],
    "recruiter_concerns": []
  }}
}}

STRICT OUTPUT RULES:
* Output MUST be valid JSON.
* Output ONLY JSON.
* No markdown.
* No code blocks.
* No comments.
* No explanations outside JSON.
* Do NOT change keys.
* Preserve extracted resume data.
* Use "" for missing values.
* Use [] for empty arrays.

grammar_and_spelling_mistakes:
* Extract exact text containing the issue.
* Provide corrected version.
* Explain the issue briefly.

content_improvements:
* Rewrite weak content professionally.
* Improve clarity.
* Improve readability.
* Improve impact.
* Use strong action verbs.
* Make content recruiter-friendly.

Experience descriptions:
* Must be concise.
* Must be professional.
* Must be achievement-focused where possible.

Return ALL issues found throughout the resume.
"""

    if not client:
        logger.error("Groq client is not initialized. Check GROQ_API_KEY.")
        return {
            "error": "Groq API key not configured",
            "personal_info": {"name": "", "email": "", "phone": "", "linkedin": "", "github": "", "portfolio": ""},
            "summary": "", "skills": [], "experience": [], "projects": [], "education": [], "certifications": [],
            "analysis": {"grammar_and_spelling_mistakes": [], "content_improvements": [], "improvements_to_stand_out": [], "formatting_and_structure_feedback": "", "missing_information": [], "recruiter_concerns": []}
        }

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=4096
    )

    content = response.choices[0].message.content.strip()

    fallback_schema = {
        "personal_info": {"name": "", "email": "", "phone": "", "linkedin": "", "github": "", "portfolio": ""},
        "summary": "",
        "skills": [],
        "experience": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "analysis": {
            "grammar_and_spelling_mistakes": [],
            "content_improvements": [],
            "improvements_to_stand_out": [],
            "formatting_and_structure_feedback": "",
            "missing_information": [],
            "recruiter_concerns": []
        }
    }

    result = _clean_and_parse_json(content, fallback_schema)

    if isinstance(result, dict) and not result.get("error"):
        p_info = result.get("personal_info", {})
        analysis = result.get("analysis", {})
        logger.info(
            "Parsed Groq result summary: name='%s', skills=%d, experience=%d, projects=%d, grammar_errors=%d, improvements=%d",
            p_info.get("name") if isinstance(p_info, dict) else "",
            len(result.get("skills", [])) if isinstance(result.get("skills"), list) else 0,
            len(result.get("experience", [])) if isinstance(result.get("experience"), list) else 0,
            len(result.get("projects", [])) if isinstance(result.get("projects"), list) else 0,
            len(analysis.get("grammar_and_spelling_mistakes", [])) if isinstance(analysis, dict) and isinstance(analysis.get("grammar_and_spelling_mistakes"), list) else 0,
            len(analysis.get("content_improvements", [])) if isinstance(analysis, dict) and isinstance(analysis.get("content_improvements"), list) else 0
        )

    return result


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
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    content = response.choices[0].message.content.strip()
    return _clean_and_parse_json(content)

# ==========================
# AI POLISH
# ==========================

def optimize_text_with_groq(text, text_type="general"):
    prompt = f"""
You are a senior resume writer with 15+ years of recruiting experience.

TASK:
Rewrite the content professionally.

Rules:

ATS optimized
Professional
Grammar perfect
Strong action verbs
Concise
Impact focused
Keep same meaning
Do not invent information
Use recruiter-friendly language
Use modern resume style

If TYPE is "summary":
- 3 to 5 lines maximum
- Professional paragraph
- ATS optimized
- Include JD keywords naturally
- No bullet points
- No first-person language
- Strong value proposition

If TYPE is "experience":
EXPERIENCE RULES:
- MUST return bullet points
- Each bullet starts with •
- 3 to 6 bullets per role
- Every bullet begins with a strong action verb
Examples:
• Developed scalable REST APIs serving 100K+ users.
• Automated deployment workflows reducing release time by 60%.
• Optimized PostgreSQL queries improving response times by 35%.

DO NOT RETURN PARAGRAPHS.
DO NOT MERGE BULLETS INTO ONE PARAGRAPH.

If TYPE is "projects":
PROJECT RULES:
- MUST return bullet points
- Each bullet starts with •
- 2 to 5 bullets per project
- Mention technologies naturally
- Mention measurable outcomes if available
Example:
• Built a resume optimization platform using Flask and PostgreSQL.
• Implemented AI-powered ATS scoring using Groq LLM APIs.
• Reduced resume processing time by 40% through query optimization.

DO NOT RETURN PARAGRAPHS.

TEXT TYPE:
{text_type}

TEXT:
{text}

OUTPUT:
Return ONLY the rewritten text.
No explanations.
No markdown.
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )

    optimized = response.choices[0].message.content.strip()

    if text_type.lower() in ["experience", "projects"]:

        # If AI returned paragraph instead of bullets
        if "•" not in optimized:

            sentences = [
                s.strip()
                for s in re.split(r'[.\n]+', optimized)
                if s.strip()
            ]

            optimized = "\n".join(
                [f"• {sentence}" for sentence in sentences]
            )

    return optimized


# ==========================
# RESUME TAILORING
# ==========================

def tailor_resume_with_groq(resume_data, job_desc):

  def force_bullets(text):

    if not text:
        return ""

    # Handle list returned by AI
    if isinstance(text, list):

        bullets = []

        for item in text:

            item = str(item).strip()

            if not item:
                continue

            item = item.lstrip("•*- ")

            bullets.append(f"• {item}")

        return "\n".join(bullets)

    # Convert to string
    text = str(text).strip()

    # Remove accidental list formatting
    if text.startswith("[") and text.endswith("]"):

        try:
            import ast

            parsed = ast.literal_eval(text)

            if isinstance(parsed, list):

                bullets = []

                for item in parsed:

                    item = str(item).strip()

                    if not item:
                        continue

                    item = item.lstrip("•*- ")

                    bullets.append(f"• {item}")

                return "\n".join(bullets)

        except:
            pass

    # Already multiline bullets
    if "\n" in text:

        bullets = []

        for line in text.split("\n"):

            line = line.strip()

            if not line:
                continue

            line = line.lstrip("•*- ")

            bullets.append(f"• {line}")

        return "\n".join(bullets)

    # Convert paragraph into bullets
    sentences = [
        s.strip()
        for s in re.split(r'[.\n]+', text)
        if s.strip()
    ]

    return "\n".join(
        [f"• {sentence}" for sentence in sentences]
    )



  prompt = f"""

  ROLE:
  You are a world-class resume strategist, ATS optimization expert, FAANG recruiter, and hiring manager.

  GOAL:
  Transform the candidate's resume to maximize ATS score and recruiter appeal for the target job description.

  STRICT RULES:

  1. NEVER invent:

  * Experience
  * Companies
  * Projects
  * Skills
  * Certifications
  * Technologies
  * Achievements

  2. ONLY improve existing content.

  3. Preserve factual accuracy.

  4. Rewrite content using strong action verbs.

  5. Quantify achievements whenever possible.

  6. Integrate relevant job-description keywords naturally.

  7. Prioritize ATS optimization.

  8. Remove weak phrases:

  * Responsible for
  * Worked on
  * Helped with
  * Participated in
  * Involved in

  Replace with:

  * Developed
  * Engineered
  * Built
  * Designed
  * Implemented
  * Automated
  * Led
  * Optimized
  * Improved
  * Reduced
  * Increased
  * Delivered

  SUMMARY RULES:

  * 3 to 5 lines
  * ATS optimized
  * Recruiter friendly
  * Keyword rich
  * Professional paragraph
  * NO bullet points

  EXPERIENCE RULES:

  * description MUST contain bullet points
  * Every bullet starts with •
  * 3 to 6 bullets per role
  * Use strong action verbs
  * Show measurable impact
  * No paragraphs
  * No numbering

  PROJECT RULES:

  * description MUST contain bullet points
  * Every bullet starts with •
  * 2 to 5 bullets per project
  * Highlight technologies
  * Highlight business value
  * Highlight performance or scale
  * No paragraphs
  * No numbering

  SKILLS RULES:

  * Keep existing skills
  * Add JD keywords ONLY if supported by resume
  * Do not hallucinate skills

  ATS OPTIMIZATION:

  * Extract top ATS keywords from Job Description
  * Distribute naturally across:

    * Summary
    * Experience
    * Projects
    * Skills

  JSON STRUCTURE RULE:
  The output JSON structure MUST remain identical to the input JSON.

  JOB DESCRIPTION:

  {job_desc}

  ORIGINAL RESUME JSON:

  {json.dumps(resume_data, indent=2)}

  RETURN:
  ONLY VALID JSON.
  NO MARKDOWN.
  NO EXPLANATIONS.
  NO NOTES.
  """


  response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
      {
        "role": "user",
        "content": prompt
      }
      ],
      temperature=0.3
    )

  content = response.choices[0].message.content.strip()

  try:
      tailored = json.loads(content)

  except:
      match = re.search(r'\{[\s\S]*\}', content)

      if match:
        try:
          tailored = json.loads(match.group())
        except:
          return resume_data
      else:
          return resume_data

     
  # Force bullets in Experience
  for exp in tailored.get("experience", []):

      if exp.get("description"):
          exp["description"] = force_bullets(
              exp["description"]
          )

  # Force bullets in Projects
  for project in tailored.get("projects", []):

      if project.get("description"):
          project["description"] = force_bullets(
              project["description"]
          )

  return tailored




# ==========================
# KEYWORD ANALYSIS
# ==========================

def analyze_keywords_with_groq(resume_data, job_desc):

    prompt = f"""
You are an ATS keyword analyzer.

JOB DESCRIPTION:
{job_desc}

RESUME:
{json.dumps(resume_data)}

TASK:

1. Extract top 30 ATS keywords from the JD.

2. Compare against the resume.

3. Ignore filler words.

4. Match:

   * Skills
   * Technologies
   * Frameworks
   * Methodologies
   * Certifications
   * Soft skills

OUTPUT FORMAT:

{{
"matched":[],
"missing":[]
}}

RULES:

* matched = keywords found in resume
* missing = important JD keywords absent from resume
* no duplicates
* no explanations
* return valid JSON only

"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except:
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            return json.loads(match.group())

    return {
        "matched": [],
        "missing": []
    }


def parse_resume_to_json_with_groq(resume_text):
    prompt = f"""
ROLE:
You are an expert resume parsing system. Your task is to extract all information from the provided resume text and map it to the exact target JSON schema below.

TARGET SCHEMA:
{{
  "first_name": "extracted first name or empty string",
  "last_name": "extracted last name or empty string",
  "job_title": "extracted target or current job title or empty string",
  "email": "extracted email or empty string",
  "phone": "extracted phone number or empty string",
  "location": "extracted city, state/country or empty string",
  "linkedin": "extracted LinkedIn URL or username or empty string",
  "github": "extracted GitHub profile link or username or empty string",
  "portfolio": "extracted portfolio URL or empty string",
  "summary": "extracted profile summary or empty string",
  "experience": [
    {{
      "company": "company name",
      "role": "job title",
      "location": "city, state",
      "start_date": "YYYY-MM-DD format (use best estimate or empty string)",
      "end_date": "YYYY-MM-DD format (use best estimate or empty string if current)",
      "current": true/false (boolean, set to true if current role, false otherwise),
      "description": "extracted responsibilities and achievements as bullet points starting with \u2022 or * (separated by newlines)"
    }}
  ],
  "projects": [
    {{
      "name": "project name",
      "role": "role in project (e.g. Lead Developer)",
      "link": "project link or repository url or empty string",
      "start_date": "YYYY-MM-DD format",
      "end_date": "YYYY-MM-DD format",
      "description": "project details as bullet points",
      "technologies": "comma-separated list of technologies used (e.g. Python, Flask, Docker)"
    }}
  ],
  "education": [
    {{
      "school": "institution name",
      "degree": "degree name (e.g. Bachelor of Science)",
      "field": "field of study (e.g. Computer Science)",
      "start_date": "YYYY-MM-DD format",
      "end_date": "YYYY-MM-DD format",
      "gpa": "extracted GPA or percentage or empty string"
    }}
  ],
  "skills": [
    {{
      "category": "category name (e.g. Languages, Tools)",
      "list": "comma-separated list of skills in this category"
    }}
  ],
  "certifications": [
    {{
      "name": "certification name",
      "issuer": "issuing organization or empty string"
    }}
  ],
  "languages": [
    {{
      "language": "language name",
      "level": "proficiency level"
    }}
  ],
  "achievements": [
    {{
      "title": "achievement detail"
    }}
  ]
}}

STRICT RULES:
1. Return ONLY the JSON object. Do not include markdown code block syntax (like ```json ... ```) or any trailing explanations.
2. If any field or section is not present in the resume, return empty string "" or empty array [] as defined by the schema.
3. Convert all dates to YYYY-MM-DD format. If only a year is available, assume January 1st (e.g., "2020" -> "2020-01-01").
4. Maintain clean formatting for experience and project description bullet points.

RESUME TEXT:
{resume_text}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except Exception:
        # Fallback if markdown block is present
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        return {"error": "Could not parse JSON response from AI", "raw": content}