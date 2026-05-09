from tools.logger import logger
import json
import re
from tools.browser_llm import BrowserLLM

class CareerAdvisor:
    def __init__(self, db=None):
        self._browser_llm = None
        self.db = db

    def _get_llm(self):
        if self._browser_llm is None:
            # Load headless setting from bot config if db is available
            headless = True
            if self.db:
                config = self.db.load_bot_config()
                headless = config.get("settings", {}).get("ai_headless", True)
            
            # Career suggestions run with the configured headless mode
            self._browser_llm = BrowserLLM(provider="ChatGPT", headless=headless)
        return self._browser_llm

    def close(self):
        if self._browser_llm:
            self._browser_llm.close_tab()
            self._browser_llm = None

    def _clean_json_array(self, text: str) -> list[str]:
        """Extracts a JSON array of strings from LLM output."""
        if not text or not isinstance(text, str):
            return []

        try:
            # 1. Try finding Markdown code blocks - take the LAST one (response) to avoid prompt examples
            matches = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
            if matches:
                for inner_text in reversed(matches):
                    try:
                        parsed = json.loads(inner_text.strip())
                        if isinstance(parsed, list) and len(parsed) > 0:
                            if not ("Title 1" in parsed and "Title 2" in parsed):
                                return [str(x) for x in parsed]
                    except:
                        pass

            # 2. Find the largest valid JSON array [...], searching from bottom up
            # to avoid picking up example arrays from the prompt text
            starts = [i for i, char in enumerate(text) if char == '[']
            for start in reversed(starts):
                count = 0
                for i in range(start, len(text)):
                    if text[i] == '[':
                        count += 1
                    elif text[i] == ']':
                        count -= 1

                    if count == 0:
                        potential_json = text[start:i+1]
                        try:
                            # Cleanup trailing commas before parsing
                            potential_json = re.sub(r",\s*\]", "]", potential_json)
                            data = json.loads(potential_json)
                            if isinstance(data, list) and len(data) > 0:
                                # Ensure we don't return the example ["Title 1", "Title 2"]
                                if "Title 1" in data and "Title 2" in data:
                                    continue
                                return [str(x) for x in data]
                        except:
                            pass
                        break

            return []
        except Exception as e:
            logger.error(f"Advisor JSON Clean Failed: {e}")
            return []

    def suggest_roles(self, resume_text: str) -> list[str]:
        """
        Analyzes the resume and suggests 5 job titles to search for.
        """
        if not resume_text or len(resume_text) < 50:
            return []

        try:
            # Reusing the browser instance significantly speeds up batch processing
            llm = self._get_llm()

            prompt = f"""
SYSTEM: You are a strict Career Advisor. You ONLY analyze resumes and suggest job titles.
TASK: Analyze the following resume and suggest strictly 5 specific job titles.
FORMAT: Strictly a JSON array of strings, e.g. ["Title 1", "Title 2"].

RESUME:
{resume_text[:4000]}

OUTPUT ONLY THE JSON ARRAY.
"""
            # ']' signals the end of a JSON array like ["Title 1", "Title 2"]
            content = llm.ask(prompt, done_signal=']')

            logger.info(f"ADVISOR RAW RESPONSE: {content}")

            suggestions = self._clean_json_array(content)

            if not suggestions:
                # Log correctly but return empty to let UI handle the error
                logger.warning(f"Advisor failed to parse LLM output for resume ({len(resume_text)} chars).")
                return []

            return suggestions[:5]

        except Exception as e:
            logger.error(f"Advisor Error: {e}")
            return []

    def generate_outreach_message(self, resume_text: str) -> str:
        """
        Generates a 2-3 line outreach message based on the resume.
        """
        if not resume_text or len(resume_text) < 50:
            return ""

        try:
            llm = self._get_llm()

            prompt = f"""
SYSTEM: You are a professional career coach.
TASK: Write a respectful LinkedIn outreach message to a 1st-degree connection asking for projects or job matches that fit the user's credentials.
CONSTRAINTS:
- Length: Strictly 2 to 3 lines.
- Tone: Professional and respectful.
- Placeholders: Use {{first_name}} for the recipient's name.
- Content: Based on the following resume summary.

RESUME:
{resume_text[:2000]}

OUTPUT ONLY THE MESSAGE CONTENT. NO PREAMBLE.
"""
            # Outreach is plain text — any non-trivial content signals completion
            content = llm.ask(prompt, done_signal='.')
            # Remove any quotes or preamble if LLM added them
            content = content.strip().strip('"').strip("'")
            return content

        except Exception as e:
            logger.error(f"Advisor Outreach Generation Error: {e}")
            return ""
