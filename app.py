import os
# Must be set BEFORE importing crewai to avoid Telemetry/Signal errors
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

import streamlit as st
from ui.sidebar import render_sidebar
from ui.home_view import render_home_view
from ui.explorer_view import render_explorer_view
from ui.applied_view import render_applied_view
from ui.networking_view import render_networking_view
from ui.bot_settings_view import render_bot_settings_view
from job_hunter.data_manager import DataManager

# --- Page Config ---
st.set_page_config(
    page_title="CareerCommander",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Session State Init ---
def init_session_state():
    db = DataManager()
    if 'page' not in st.session_state: st.session_state['page'] = 'home'
    if 'resumes' not in st.session_state: st.session_state['resumes'] = {}
    if 'job_cache' not in st.session_state: st.session_state['job_cache'] = db.load_cache()
    if 'applied_jobs' not in st.session_state: st.session_state['applied_jobs'] = db.load_applied()
    if 'scrape_location' not in st.session_state: st.session_state['scrape_location'] = "Germany"
    if 'analysis_results' not in st.session_state: st.session_state['analysis_results'] = {}
    if 'selected_job_id' not in st.session_state: st.session_state['selected_job_id'] = None
    if 'chat_history' not in st.session_state: st.session_state['chat_history'] = {}
    
    # Load resumes from disk if any
    if not st.session_state['resumes']:
        load_resume_config()

def load_resume_config():
    db = DataManager()
    st.session_state['resumes'] = db.load_resume_config()

def main():
    init_session_state()
    render_sidebar()
    
    page = st.session_state['page']
    
    if page == 'home':
        render_home_view()
    elif page == 'explorer':
        render_explorer_view()
    elif page == 'applied':
        render_applied_view()
    elif page == 'networking':
        render_networking_view()
    elif page == 'bot_settings':
        render_bot_settings_view()

if __name__ == "__main__":
    main()
