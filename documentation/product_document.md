# CareerCommander (Mini) - Product Documentation

## 🎯 What it is for
CareerCommander is an automated, AI-powered job application engine and tracking platform. It is designed to completely eliminate the manual, repetitive grind of job hunting by automating the process of finding jobs, tailoring applications, and submitting them.

## ✨ What does it do
*   **Job Scouting**: Automatically scrapes job boards (LinkedIn, Indeed, Xing) for open positions based on your specific keywords and locations.
*   **AI Resume Analysis**: Compares scraped Job Descriptions (JDs) directly against your resume to provide an ATS match score.
*   **Asset Generation**: Uses AI to automatically draft highly-tailored cover letters and rewrite your resume experience bullets to perfectly match the JD's keywords.
*   **Automated Applications (Vision Mode)**: Uses computer vision and browser automation to physically apply to "Easy Apply" jobs on your behalf.
*   **Pipeline Management**: Provides a clean UI dashboard to track which jobs are pending, which have been applied to, and allows blacklisting/banning companies you want to avoid.
*   **Smart Resume Mapping**: Allows you to upload multiple versions of your resume and assign different versions to different job titles.

## ⚙️ How it does it
*   **Tech Stack**: Built completely in Python, featuring a lightweight interactive frontend powered by **Streamlit**.
*   **Browser Automation**: Utilizes **Selenium (Undetected ChromeDriver)** to drive headless browsers that interact with job boards and bypass basic bot protections.
*   **Cost-Free AI Architecture (BrowserLLM)**: Instead of paying expensive per-token API costs, the system securely opens a browser tab, navigates to consumer AI platforms (like ChatGPT or Gemini), injects the prompt via JavaScript, waits for the generation to complete, and extracts the raw JSON response directly from the HTML elements.
*   **Local Database**: Uses a lightweight, local JSON-based file architecture (`data/scouted_jobs.json`, `data/analysis_cache.json`, etc.) to store job data, ensuring total data privacy without requiring a heavy SQL backend.
*   **Background Processing**: Supports asynchronous background batches for scraping and AI analysis, meaning you can start a large job analysis mission and walk away while the bot does the heavy lifting.
