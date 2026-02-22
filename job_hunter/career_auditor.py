from datetime import datetime
from tools.browser_llm import BrowserLLM
from .data_manager import DataManager

class CareerAuditor:
    def __init__(self):
        self.dm = DataManager()

    def run_audit(self, resume_text):
        """
        Analyzes all applied jobs against the resume to find rejection patterns.
        """
        # 1. Load Applied Jobs
        applied_jobs = self.dm.load_applied()
        if not applied_jobs:
            return "No applied jobs found to analyze."

        # 2. Extract Rich Descriptions and Metadata
        job_texts = []
        dates = []
        
        for job_id, job_data in applied_jobs.items():
            details = job_data.get('job_details', {})
            description = details.get('Rich Description') or details.get('rich_description') or details.get('Job Description') or details.get('description') or ''
            title = details.get('Job Title', 'Unknown Role')
            
            # Metadata collection
            created_at = job_data.get('created_at', '')
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at)
                    dates.append(dt)
                except: pass

            if description and len(description) > 100:
                job_texts.append(f"--- JOB: {title} ---\n{description}\n")

        total_jobs = len(job_texts)
        if total_jobs < 5:
            return f"Not enough data. You have only applied to {total_jobs} jobs. Apply to at least 10-20 for a meaningful audit."

        # Calculate Tenure/Range
        date_range_str = "Unknown"
        if dates:
            min_date = min(dates).strftime("%d %B %Y")
            max_date = max(dates).strftime("%d %B %Y")
            date_range_str = f"{min_date} to {max_date}"

        analysis_date = datetime.now().strftime("%d %B %Y")

        # 3. Construct the Grand Prompt
        aggregated_jobs = "\n".join(job_texts[:30]) # Limit to 30 jobs to avoid prompt size issues
        
        prompt = f"""
You are the "Grand Master Career Strategist".
I have applied to the following {min(total_jobs, 30)} jobs and received 0 interviews.

Here is my Resume:
{resume_text}

------------------------------------------------------------
Here are the Job Descriptions I applied to:
{aggregated_jobs}
------------------------------------------------------------

TASK:
Compare my resume against the *collective requirements* of these jobs to find the "Root Cause" of my rejections.

Analyze the data and answer:

1. **The Skill Gap**: What specific technical skills or tools are consistently mentioned in these JDs that are MISSING, WEAK, or BURIED in my resume?
2. **Experience Mismatch**: Is my resume narrative (Seniority/Years) aligned with the level of these roles? Am I underselling or overselling myself?
3. **The "Killer" Requirements**: Are there recurring hard requirements (e.g. C1 German, Specific Degree) that appear in >50% of these jobs that I might be failing?
4. **Actionable Fixes**: Give me 3-5 concrete changes I must make to my resume IMMEDIATELY.

Format your response in professional Markdown. Be harsh, direct, and constructive.
"""

        # 4. Invoke LLM via Browser
        try:
            # Run audit in headless mode
            browser_llm = BrowserLLM(provider="ChatGPT", headless=True)
            raw_content = browser_llm.ask(prompt)
            browser_llm.close_tab()
            
            # 5. Prepend Metadata Header
            header = f"""# ♟️ Grand Master Strategy Report
**Analysis Date**: {analysis_date}
**Jobs Analyzed**: {total_jobs}
**Batch Tenure**: {date_range_str}

---
"""
            return header + raw_content
            
        except Exception as e:
            return f"Error running Career Audit: {str(e)}"
