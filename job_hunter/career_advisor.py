from tools.logger import logger
import json
import re
from tools.browser_llm import BrowserLLM

class CareerAdvisor:
    def __init__(self):
        self._browser_llm = None

    def _get_llm(self):
        if self._browser_llm is None:
            self._browser_llm = BrowserLLM(provider="ChatGPT")
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
            # 1. Try finding Markdown code blocks
            match = re.search(r"```(?:json)?(.*?)```", text, re.DOTALL)
            if match:
                inner_text = match.group(1).strip()
                try:
                    parsed = json.loads(inner_text)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed]
                except:
                    pass

            # 2. Find the largest valid JSON array [...]
            starts = [i for i, char in enumerate(text) if char == '[']
            for start in starts:
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
                            if isinstance(data, list):
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
            content = llm.ask(prompt)

            logger.info(f"ADVISOR RAW RESPONSE: {content}")

            suggestions = self._clean_json_array(content)

            if not suggestions:
                # Fallback if parsing fails
                logger.warning("Advisor failed to parse LLM output. Using fallbacks.")
                return ["Data Analyst", "Data Scientist", "Business Analyst", "Project Manager", "Software Engineer"]

            return suggestions[:5]

        except Exception as e:
            logger.error(f"Advisor Error: {e}")
            return ["Data Analyst", "Data Scientist", "Business Analyst", "Project Manager", "Software Engineer"]
