import json
import re
from tools.browser_llm import BrowserLLM

class CareerAdvisor:
    def suggest_roles(self, resume_text: str) -> list[str]:
        """
        Analyzes the resume and suggests 5 job titles to search for.
        """
        if not resume_text or len(resume_text) < 50:
            return []

        try:
            browser_llm = BrowserLLM(provider="ChatGPT")

            prompt = f"""
SYSTEM: You are a strict Career Advisor. You ONLY analyze resumes and suggest job titles.
TASK: Analyze the following resume and suggest strictly 5 specific job titles.
Format: strictly a JSON array of strings, e.g. ["Title 1", "Title 2"].

RESUME:
{resume_text[:4000]}
"""
            content = browser_llm.ask(prompt)
            browser_llm.close_tab()

            print(f"ADVISOR RAW: {content}")

            # 1. Try finding JSON array
            match = re.search(r"\[.*?\]", content, re.DOTALL)
            if match:
                json_str = match.group(0)
                json_str = re.sub(r",\s*\]", "]", json_str)
                parsed = json.loads(json_str)
                
                final_list = []
                for item in parsed:
                    if isinstance(item, str):
                        final_list.append(item)
                    elif isinstance(item, dict):
                        final_list.extend([v for v in item.values() if isinstance(v, str)])
                
                return final_list[:5] if final_list else []
            
            return ["Data Analyst", "Data Scientist", "Business Analyst"]
        except Exception as e:
            print(f"Advisor Error: {e}")
            return ["Data Analyst", "Data Scientist", "Business Analyst"]
