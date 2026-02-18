from tools.logger import logger
import os
import re
import json
from tools.browser_llm import BrowserLLM

class JobAnalysisCrew:
    def __init__(self, job_text: str, resume_text: str, profile_name: str = "default"):
        self.job_text = job_text
        self.resume_text = resume_text
        self.profile_name = profile_name

    def _clean_json(self, text):
        """Helper to extract JSON from LLM output if it includes markdown code blocks or conversational text."""
        if not text or not isinstance(text, str):
            return {}

        try:
            # 1. Try finding Markdown code blocks (most reliable)
            match = re.search(r"```(?:json)?(.*?)```", text, re.DOTALL)
            if match:
                inner_text = match.group(1).strip()
                try:
                    return json.loads(inner_text)
                except:
                    pass

            # 2. Find the largest valid JSON object by searching for { }
            starts = [i for i, char in enumerate(text) if char == '{']
            for start in starts:
                count = 0
                for i in range(start, len(text)):
                    if text[i] == '{':
                        count += 1
                    elif text[i] == '}':
                        count -= 1

                    if count == 0:
                        potential_json = text[start:i+1]
                        try:
                            data = json.loads(potential_json)
                            if isinstance(data, dict):
                                return data
                        except:
                            pass
                        break

            # 3. Final fallback
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except:
                    pass

            return {}
        except Exception as e:
            logger.info(f"DEBUG: JSON CLEAN FAILED: {e}")
            return {}

    def run_analysis(self, components=None, use_browser=True):
        """Runs the analysis using a browser-based LLM instead of API."""
        if components is None:
            components = ['intel', 'cover_letter', 'ats', 'resume']

        logger.info(f"[Analysis] Running browser-based analysis ({self.profile_name}) for: {components}")

        provider = os.getenv("BROWSER_LLM_PROVIDER", "ChatGPT")
        browser_llm = BrowserLLM(provider=provider, profile_name=self.profile_name)

        # Construct a combined prompt
        prompt = f"""
I need you to perform a job analysis based on the following Job Description and my Resume.

JOB DESCRIPTION:
{self.job_text}

RESUME:
{self.resume_text}

Please provide the following components in a single VALID JSON object.
Ensure the JSON is well-formatted and can be parsed.

COMPONENTS REQUESTED:
{', '.join(components)}

STRICT JSON STRUCTURE REQUIRED:
{{
"""
        if 'intel' in components:
            prompt += """  "company_intel": {
    "mission": "...",
    "key_facts": ["fact1", "fact2"],
    "headquarters": "...",
    "employees": "...",
    "branches": "..."
  },
"""
        if 'cover_letter' in components:
            prompt += """  "cover_letter": "...",
  "humanization_score": 95,
"""
        if 'ats' in components:
            prompt += """  "ats_report": {
    "score": 85,
    "missing_skills": ["skill1", "skill2"]
  },
"""
        if 'resume' in components:
            prompt += """  "tailored_resume": "### Experience\\n...",
"""

        prompt += """  "status": "success"
}

Specific Instructions:
- For 'cover_letter': Write a highly professional, direct cover letter.
  FORMAT:
  Subject: Job Application for [Job Title]
  Dear Hiring Manager,
  [Direct intro: show interest in [Job Title] at [Company]. Mention years of experience and core fields.]
  [Paragraph 2: Focus on specific technical achievements and tools.]
  [Paragraph 3: Knowledge of banking/sectors and soft skills/facilitation.]
  [Paragraph 4: Technical stack summary. Mention: "I have strong technical skills in [Stack], as well as an organized and analytical work style. My practical proficiency in English (C1 level) and decent proficiency in German (B1 level) are virtues that I constantly improve professionally."]
  [Paragraph 5: Direct closing.]
  Use NO AI transitions like "Furthermore" or "Moreover". Keep it grounded.
- For 'tailored_resume': Focus on rewriting the Experience section to match JD keywords.
- For 'ats_report': Give an honest match score from 0-100.
- Output ONLY the JSON object. No conversation.
"""

        response_text = browser_llm.ask(prompt)
        results = self._clean_json(response_text)
        browser_llm.close_tab()

        return results
