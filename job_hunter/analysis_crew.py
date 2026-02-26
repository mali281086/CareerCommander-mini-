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

        # Truncate inputs to avoid LLM limits and browser paste issues
        # 3000 chars is usually safe for most LLMs and doesn't lose critical context
        truncated_job = self.job_text[:3000] if self.job_text else ""
        truncated_resume = self.resume_text[:3000] if self.resume_text else ""

        logger.info(f"[Analysis] Running browser-based analysis for components: {components}")

        from job_hunter.data_manager import DataManager
        db = DataManager()
        bot_config = db.load_bot_config()
        # Respect headless setting from bot config, default to True
        headless = bot_config.get("settings", {}).get("ai_headless", True)

        provider = os.getenv("BROWSER_LLM_PROVIDER", "ChatGPT")
        # Run analysis using a dedicated profile to avoid interference
        browser_llm = BrowserLLM(provider=provider, profile_name="llm_profile", headless=headless)

        # Construct a combined prompt
        prompt = f"""
I need you to perform a job analysis based on the following Job Description and my Resume.

JOB DESCRIPTION:
{truncated_job}

RESUME:
{truncated_resume}

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

        if response_text.startswith("ERROR:"):
            browser_llm.close_tab()
            return {"error": response_text}

        results = self._clean_json(response_text)
        if not results:
            results = {"error": f"Failed to parse JSON from AI response. Raw response: {response_text[:200]}..."}

        browser_llm.close_tab()
        return results
