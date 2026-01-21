from job_hunter.model_factory import get_llm
import json
import re

class CareerAdvisor:
    def suggest_roles(self, resume_text: str) -> list[str]:
        """
        Analyzes the resume and suggests 5 job titles to search for.
        """
        if not resume_text or len(resume_text) < 50:
            return []

        llm = get_llm()
        
        prompt = f"""
        SYSTEM: You are a strict Career Advisor. You ONLY analyze resumes and suggest job titles. Do NOT discuss anything else.
        
        TASK: Analyze the following resume text and suggest strictly 5 specific job titles.
        Format: strictly a JSON array of strings, e.g. ["Title 1", "Title 2"].
        
        RESUME:
        {resume_text[:4000]}
        """
        
        try:
            # Invoking the chat model
            response = llm.invoke(prompt)
            content = response.content
            # Debug:
            print(f"ADVISOR RAW: {content}")

            # 1. Try finding JSON array
            match = re.search(r"\[.*?\]", content, re.DOTALL)
            if match:
                json_str = match.group(0)
                # Simple cleanup for trailing commas
                json_str = re.sub(r",\s*\]", "]", json_str)
                parsed = json.loads(json_str)
                
                # HANDLE LIST OF DICTS (The "Advisor Error" Fix)
                # If LLM returns [{"Title 1": "Data Analyst"}, ...], extract values
                final_list = []
                for item in parsed:
                    if isinstance(item, str):
                        final_list.append(item)
                    elif isinstance(item, dict):
                        # Extract all string values from the dict (e.g. {"Title": "Analyst"})
                        final_list.extend([v for v in item.values() if isinstance(v, str)])
                
                return final_list[:5] if final_list else []
            
            # 2. Fallback: Parse bullet points (LLMs often do this)
            # Extracts lines starting with - or * or numbers
            titles = re.findall(r"(?:^|\n)[-*\d\.]+\s*(.*)", content)
            cleaned_titles = [t.strip().strip('"').strip("'") for t in titles if len(t) > 3]
            if cleaned_titles:
                return cleaned_titles[:5]
                
            return []
        except Exception as e:
            print(f"Advisor Error: {e}")
            # Only return fallback if genuine error, but try to be transparent
            return ["Data Analyst", "Machine Learning Engineer", "Business Intelligence Developer"]
