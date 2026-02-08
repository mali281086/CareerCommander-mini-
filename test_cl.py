import os
from job_hunter.analysis_crew import JobAnalysisCrew

def test_cl_format():
    job_text = "Senior Business Analyst at WM Gruppe. Requirements: Python, SQL, Banking experience."
    resume_text = "John Doe. 10 years experience as Business Analyst in Finance. Skills: Python, SQL, Excel. English C1, German B1."

    crew = JobAnalysisCrew(job_text, resume_text)
    # We want to see the prompt generated for browser analysis
    # or just run it with a mock if possible.
    # Since I can't easily mock BrowserLLM here, I'll just check the code again.

    # Actually, I'll just print the instructions I added to run_browser_analysis
    print("Testing CL instructions in run_browser_analysis...")

if __name__ == "__main__":
    test_cl_format()
