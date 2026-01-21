import json
from datetime import datetime
from .model_factory import get_llm
from .data_manager import DataManager

class CareerAuditor:
    def __init__(self):
        self.llm = get_llm(return_crew_llm=False)
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
            description = details.get('Rich Description', '')
            title = details.get('Job Title', 'Unknown Role')
            
            # Metadata collection
            created_at = job_data.get('created_at', '')
            if created_at:
                try:
                    # Handle both ISO format and potential simple date strings
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
        aggregated_jobs = "\n".join(job_texts)
        
        prompt = f"""
        You are the "Grand Master Career Strategist". 
        I have applied to the following {total_jobs} jobs and received 0 interviews.
        
        Here is my Resume:
        {resume_text}

        ------------------------------------------------------------
        Here are the {total_jobs} Job Descriptions I applied to:
        {aggregated_jobs}
        ------------------------------------------------------------

        TASK:
        Compare my resume against the *collective requirements* of these jobs to find the "Root Cause" of my rejections.
        
        Analyze the data and answer:
        
        1. **The Skill Gap**: What specific technical skills or tools are consistently mentioned in these JDs that are MISSING, WEAK, or BURIED in my resume? (e.g. "80% of Analyst jobs asked for SQL, but you only mention it once.")
           *   *CRITICAL RULE*: If I have a skill that implies another (e.g. "Power BI Dashboarding" implies "DAX"), do NOT ask me to write a long paragraph explaining it. Instead, advise me to simply add the specific missing keywords (e.g. "DAX", "M-Query") to a "Technical Skills" list to satisfy ATS bots without making the resume boring.
           *   *NO NITPICKING*: Do NOT suggest changing phrasing if the meaning is already clear (e.g. don't say "Change 'Built dashboards' to 'Developed visualizations'"). That is a waste of time. Focus only on TRUE gaps.
        2. **Experience Mismatch**: Is my resume narrative (Seniority/Years) aligned with the level of these roles? Am I underselling or overselling myself?
        3. **The "Killer" Requirements**: Are there recurring hard requirements (e.g. C1 German, Specific Degree, Security Clearance) that appear in >50% of these jobs that I might be failing?
        4. **Actionable Fixes**: Give me 3-5 concrete changes I must make to my resume IMMEDIATELY. Focus on "High Impact" changes (e.g. "You are missing the 'Snowflake' keyword which is in 40% of jobs") rather than style preferences.
        
        Format your response in professional Markdown. Be harsh, direct, and constructive.
        """

        # 4. Invoke LLM
        try:
            response = self.llm.invoke(prompt)
            raw_content = response.content
            
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
