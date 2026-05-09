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

        def try_parse(json_str):
            try:
                # Cleanup trailing commas in objects and arrays before parsing
                json_str = re.sub(r",\s*\}", "}", json_str)
                json_str = re.sub(r",\s*\]", "]", json_str)
                data = json.loads(json_str)
                if isinstance(data, dict):
                    return data
            except:
                pass
            return None

        best_data = {}

        try:
            # 1. Try finding Markdown code blocks
            matches = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
            for inner_text in matches:
                data = try_parse(inner_text.strip())
                if data and len(data) > len(best_data):
                    best_data = data

            if best_data and len(best_data) >= 3: # If we have a good match from markdown, use it
                return best_data

            # 2. String-aware brace counting to extract JSON from dirty text
            # We want to find the LARGEST valid JSON object (likely the root)
            starts = [i for i, char in enumerate(text) if char == '{']

            for start in starts:
                count = 0
                in_string = False
                escape = False
                
                for i in range(start, len(text)):
                    c = text[i]
                    
                    if escape:
                        escape = False
                        continue
                        
                    if c == '\\': # Fixed escape check
                        escape = True
                        continue
                        
                    if c == '"':
                        in_string = not in_string
                        continue
                        
                    if not in_string:
                        if c == '{': count += 1
                        elif c == '}': count -= 1
                        
                        if count == 0:
                            potential_json = text[start:i+1]
                            data = try_parse(potential_json)
                            if data and len(data) > len(best_data):
                                best_data = data
                            break # Move to next 'start'

            if best_data:
                return best_data

            # 3. Final fallback: Extreme match
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                data = try_parse(text[start:end+1])
                if data: return data

            return {}
        except Exception as e:
            logger.info(f"DEBUG: JSON CLEAN FAILED: {e}")
            return {}

    def run_analysis(self, components=None, use_browser=True, close_after=True, browser_llm=None, clear_chat=True, analysis_id=None):
        """Runs the analysis using a browser-based LLM instead of API."""
        if components is None:
            components = ['intel', 'cover_letter', 'ats', 'resume']

        # Truncate inputs to avoid LLM limits and browser paste issues
        truncated_job = self.job_text[:3000] if self.job_text else ""
        truncated_resume = self.resume_text[:3000] if self.resume_text else ""

        logger.info(f"[Analysis] Running browser-based analysis for components: {components}")

        from job_hunter.data_manager import DataManager
        db = DataManager()
        bot_config = db.load_bot_config()
        # Respect headless setting from bot config
        headless = bot_config.get("settings", {}).get("ai_headless", True)

        provider = os.getenv("BROWSER_LLM_PROVIDER", "ChatGPT")
        
        # Reuse existing browser session if provided
        if browser_llm is None:
            browser_llm = BrowserLLM(provider=provider, profile_name="llm_profile", headless=headless)
        
        if clear_chat:
            browser_llm.new_chat()

        # Unique Analysis ID to prevent LLM from being "lazy" and referring to previous context
        import uuid
        if analysis_id is None:
            analysis_id = str(uuid.uuid4())[:8]

        # Construct a combined prompt
        prompt = f"""
ANALYSIS_ID: {analysis_id}

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
  "fit_report": {
    "score": 90,
    "fit_analysis": "Brief reasoning for the fit score."
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
- For 'ats_report': Perform a binary keyword match. If a mandatory skill or tool from the JD is not explicitly found in the resume, it is MISSING. Score is the percentage of JD 'must-have' keywords present in the resume.
- For 'fit_report': You are an EXTREMELY STRICT, cynical hiring manager. Provide a "Resume Fit" score from 0-100. Be brutal: if core requirements (years of experience, specific senior-level tools, or industry domain) are missing, penalize heavily. A score of 80+ should be rare. In 'fit_analysis', explicitly list the candidate's biggest weaknesses or gaps compared to the JD.
- Output ONLY the JSON object. No conversation.
- DO NOT use "..." or "refer to previous" placeholders. You MUST provide the full content for every field.
"""

        max_retries = 2
        for attempt in range(max_retries + 1):
            response_text = browser_llm.ask(prompt, timeout=400)

            if response_text.startswith("ERROR:"):
                # If it's a hard crash of the browser, try to recreate and retry
                if "invalid session id" in response_text.lower() or "stacktrace:" in response_text.lower() or "element not interactable" in response_text.lower():
                    if attempt < max_retries:
                        logger.warning(f"[AnalysisCrew] Browser crash detected: {response_text[:100]}. Retrying ({attempt+1}/{max_retries})...")
                        # Force close the corrupted driver via BrowserManager
                        from tools.browser_manager import BrowserManager
                        BrowserManager().close_driver()
                        # Recreate BrowserLLM with a completely fresh driver
                        browser_llm = BrowserLLM(provider=provider, profile_name="llm_profile", headless=headless)
                        browser_llm.new_chat()
                        continue
                
                if close_after:
                    browser_llm.close_tab()
                return {"error": response_text}
            
            # If we succeed without an ERROR string, break out of retry loop
            break

        results = self._clean_json(response_text)
        
        # Check for "lazy" or empty responses and retry once if needed
        is_empty = not results or (isinstance(results, dict) and len(results) <= 1 and "status" in results)
        lazy_count = response_text.count("...")
        is_lazy = lazy_count > 5 and len(response_text) < 1000

        if (is_empty or is_lazy) and not close_after:
             logger.warning(f"[AnalysisCrew] Response was {'empty' if is_empty else 'lazy'}. Retrying with new chat...")
             browser_llm.new_chat()
             response_text = browser_llm.ask(prompt, timeout=400)
             results = self._clean_json(response_text)

        if not results or (isinstance(results, dict) and len(results) <= 1 and "status" in results):
            snippet = response_text[:200].replace('\n', ' ')
            logger.error(f"[AnalysisCrew] Failed to parse meaningful JSON. Raw response snippet: {snippet}")
            if close_after:
                browser_llm.close_tab()
            
            error_msg = "AI returned an empty or unparseable response."
            if "login" in response_text.lower() or "sign up" in response_text.lower():
                error_msg += " It looks like the AI provider is asking for a login even in Guest mode."
            
            return {"error": error_msg}
        
        # Trigger PDF generation if cover letter was returned
        if "cover_letter" in results and results["cover_letter"]:
            from tools.pdf_generator import generate_cover_letter_pdf
            # Load custom path from settings
            bot_config = db.load_bot_config()
            custom_path = bot_config.get("settings", {}).get("cover_letter_path")
            generate_cover_letter_pdf(results["cover_letter"], output_path=custom_path)

        if close_after:
            browser_llm.close_tab()
            
        return results
