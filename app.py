import os
import streamlit as st
from dotenv import load_dotenv

# Project Imports
from job_hunter.data_manager import DataManager
from job_hunter.mission_state import MissionProgress
from tools.browser_manager import BrowserManager

# View Imports
from ui.home_view import render_home_view
from ui.explorer_view import render_explorer_view
from ui.applied_view import render_applied_view
from ui.networking_view import render_networking_view
from ui.settings_view import render_settings_view

# Load envs
load_dotenv()

# Page Config
st.set_page_config(page_title="CareerCommander", layout="wide", page_icon="🚀")

# Initialize Data Manager (Global)
db = DataManager()

# Initialize Session State
if 'page' not in st.session_state: st.session_state['page'] = 'home'
if 'resumes' not in st.session_state: st.session_state['resumes'] = db.load_resume_config()
if 'applied_jobs' not in st.session_state: st.session_state['applied_jobs'] = db.load_applied()
if 'job_cache' not in st.session_state: st.session_state['job_cache'] = db.load_cache()

def navigate_to(page):
    st.session_state['page'] = page
    st.rerun()

# Sidebar
with st.sidebar:
    # --- MISSION STATUS WIDGET ---
    progress = MissionProgress.load()
    if progress.is_active:
        with st.expander(f"🛰️ Active Mission: {progress.mission_type}", expanded=True):
            st.write(f"**Status:** {progress.status}")
            cols = st.columns(2)
            cols[0].metric("Applied", progress.jobs_applied)
            cols[1].metric("Scouted", progress.jobs_scouted)

            if progress.total_steps > 0:
                perc = min(progress.current_step / progress.total_steps, 1.0)
                st.progress(perc, text=f"Progress: {progress.current_step}/{progress.total_steps}")

            if progress.pending_question:
                st.warning(f"⚠️ Action Required: {progress.pending_question}")
                if st.button("I've answered it", key="resolve_pending"):
                    progress.update(pending_question=None)
                    st.rerun()

            if st.button("🛑 Stop Mission", use_container_width=True):
                progress.reset()
                BrowserManager().close_all_drivers()
                st.rerun()
        st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("Logo.png", width=120)

    st.markdown("---")
    if st.button("🏠 Home / Launch", use_container_width=True): navigate_to('home')
    if st.button("🔎 Explorer / Scouted", use_container_width=True): navigate_to('explorer')
    if st.button("📂 Applied Jobs", use_container_width=True): navigate_to('applied')
    if st.button("🤝 Networking", use_container_width=True): navigate_to('networking')
    if st.button("⚙️ Bot Settings", use_container_width=True): navigate_to('settings')

    st.markdown("---")
    # --- BOT SETUP (Login) ---
    with st.expander("🛠️ Bot Setup (Login)", expanded=False):
        st.caption("Open browser to log into LinkedIn, Xing, etc.")
        if st.button("🔓 Open Browser & Login", use_container_width=True):
            bm = BrowserManager()
            driver = bm.get_driver(headless=False, profile_name="default")
            urls = [
                "https://www.linkedin.com/login",
                "https://login.xing.com/",
                "https://secure.indeed.com/account/login",
                "https://www.stepstone.de/candidate/login",
                "https://www.ziprecruiter.com/login"
            ]

            # Open the first URL in the current window
            driver.get(urls[0])

            # Open subsequent URLs in new tabs
            for url in urls[1:]:
                try:
                    driver.switch_to.new_window('tab')
                    driver.get(url)
                except Exception as e:
                    # Fallback for older selenium if needed, though we have 4.41
                    driver.execute_script(f"window.open('{url}', '_blank');")

            st.toast("✅ 5 Login tabs opened!")
            
        if st.button("🔒 Close Browser", use_container_width=True):
            BrowserManager().close_all_drivers()
            st.toast("Browser Closed.")

# --- RENDER VIEW ---
if st.session_state['page'] == 'home':
    render_home_view(db)
elif st.session_state['page'] == 'explorer':
    render_explorer_view(db)
elif st.session_state['page'] == 'applied':
    render_applied_view(db)
elif st.session_state['page'] == 'networking':
    render_networking_view()
elif st.session_state['page'] == 'settings':
    render_settings_view(db)
