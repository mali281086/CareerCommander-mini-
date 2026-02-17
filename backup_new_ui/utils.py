import streamlit as st
import pandas as pd
from job_hunter.data_manager import DataManager
from job_hunter.models import JobRecord

def navigate_to(page):
    st.session_state['page'] = page
    st.rerun()

def load_and_normalize_data():
    db = DataManager()
    data = db.load_scouted()
    if not data: return pd.DataFrame()

    df = pd.DataFrame(data)

    # Map internal keys to UI labels
    rename_map = {
        "title": "Job Title",
        "company": "Company",
        "location": "Location",
        "link": "Web Address",
        "platform": "Platform",
        "description": "Job Description",
        "rich_description": "Rich Description",
        "language": "Language",
        "is_easy_apply": "Easy Apply",
        "search_keyword": "Found_job"
    }
    df = df.rename(columns=rename_map)

    # Ensure required columns exist for the UI
    required = ["Job Title", "Company", "Location", "Web Address", "Platform", "Found_job", "Easy Apply", "Language"]
    for col in required:
        if col not in df.columns:
            if col == "Easy Apply":
                df[col] = False
            else:
                df[col] = "Unknown"

    if "Easy Apply" in df.columns:
        df["Easy Apply"] = df["Easy Apply"].apply(lambda x: True if x is True or str(x).lower() == 'true' else False)

    return df

def get_job_status(row, applied_jobs):
    jid = f"{row['Job Title']}-{row['Company']}"
    if jid in applied_jobs: return "✅ Applied"
    return ""
