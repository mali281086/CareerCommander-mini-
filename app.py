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

    # If not active but has tasks from last run, show a summary
    if not progress.is_active and progress.tasks:
        with st.expander("📊 Last Mission Summary", expanded=False):
            st.write(f"**Type:** {progress.mission_type}")
            st.write(f"**Status:** {progress.status}")
            st.write(f"✅ Applied: {progress.jobs_applied}")
            st.write(f"🛰️ Scouted: {progress.jobs_scouted}")
            if st.button("Clear Summary", use_container_width=True):
                progress.reset()
                st.rerun()

    if progress.is_active:
        with st.expander(f"🛰️ Active Mission: {progress.mission_type}", expanded=True):
            st.write(f"**Status:** {progress.status}")
            st.caption(f"Phase: {progress.phase}")

            cols = st.columns(2)
            cols[0].metric("Applied", progress.jobs_applied)
            cols[1].metric("Scouted", progress.jobs_scouted)

            if progress.total_steps > 0:
                perc = min(progress.current_step / progress.total_steps, 1.0)
                st.progress(perc, text=f"Progress: {progress.current_step}/{progress.total_steps}")

            # Tasks List
            if progress.tasks:
                st.markdown("---")
                st.caption("Mission Roadmap:")
                with st.container(height=300):
                    for i, task in enumerate(progress.tasks):
                        label = task.get('label')
                        is_current = (i == progress.current_task_idx)

                        if task.get('completed'):
                            st.markdown(f"✅ ~~{i+1}. {label}~~")
                        elif is_current:
                            st.markdown(f"🟡 **{i+1}. {label}**")
                        else:
                            st.markdown(f"⚪ {i+1}. {label}")

            # Control Buttons
            from job_hunter.mission_manager import MissionManager
            mm = MissionManager(db)

            c1, c2 = st.columns(2)
            if progress.is_paused:
                if c1.button("▶️ Resume", use_container_width=True):
                    progress.update(is_paused=False, status="Resuming...")
                    st.rerun()
            else:
                if c1.button("⏸️ Pause", use_container_width=True):
                    progress.update(is_paused=True, status="Paused (Manual)")
                    st.rerun()

            if c2.button("🛑 Stop", use_container_width=True, help="Stop mission and clear progress list."):
                progress.reset()
                BrowserManager().close_all_drivers()
                st.rerun()

            if st.button("💀 Kill Mission & Clear Data", use_container_width=True, type="secondary", help="Stop everything and DELETE all scouted jobs."):
                mm.kill_mission()
                st.toast("💥 Mission killed and scouted jobs cleared!")
                st.rerun()

            if progress.pending_question:
                st.warning(f"⚠️ Action Required: {progress.pending_question}")
                if st.button("I've answered it", key="resolve_pending"):
                    progress.update(pending_question=None)
                    st.rerun()
        st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if os.path.exists("Logo.png"):
            st.image("Logo.png", width=120)
        else:
            st.markdown("### 🚀 CareerCommander")

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

            # Open first URL and try loading cookies
            driver.get(urls[0])
            bm.load_cookies()

            # Open subsequent URLs in new tabs and load cookies for each
            for url in urls[1:]:
                try:
                    driver.switch_to.new_window('tab')
                    driver.get(url)
                    bm.load_cookies()
                except Exception as e:
                    # Fallback for older selenium if needed
                    try:
                        driver.execute_script(f"window.open('{url}', '_blank');")
                    except Exception as e2:
                        import logging
                        logging.getLogger("CareerCommander").warning(f"Failed to open tab for {url}: {e2}")

            st.toast("✅ 5 Login tabs opened & Sessions restored!")

        if st.button("🧠 Login to AI (ChatGPT/Gemini)", use_container_width=True):
            bm = BrowserManager()
            # AI uses a separate profile to avoid session conflicts
            driver = bm.get_driver(headless=False, profile_name="llm_profile")
            driver.get("https://chatgpt.com")
            try:
                driver.switch_to.new_window('tab')
                driver.get("https://gemini.google.com")
            except:
                driver.execute_script("window.open('https://gemini.google.com', '_blank');")
            st.toast("✅ AI Profile opened! Please log in to ChatGPT/Gemini.")
            
        if st.button("💾 Save Session Cookies", use_container_width=True):
            bm = BrowserManager()
            bm.save_cookies()
            st.toast("✅ All session cookies saved!")

        if st.button("🔒 Close Browser", use_container_width=True):
            bm = BrowserManager()
            bm.save_cookies()
            bm.close_all_drivers()
            st.toast("Browser Closed & Session Saved.")

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
