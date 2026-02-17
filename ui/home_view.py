import streamlit as st
import time
import random
import os
from datetime import datetime
from job_hunter.analysis_crew import JobAnalysisCrew
from tools.browser_manager import BrowserManager

def render_home_view(db):
    st.title("🚀 CareerCommander (Mini)")
    st.markdown("Automate your job search across LinkedIn, Indeed, Xing, and more.")

    # --- 1. RESUME MANAGEMENT ---
    st.subheader("📄 Resume Management")

    col_up, col_list = st.columns([1, 1])

    with col_up:
        uploaded_files = st.file_uploader("Upload Resumes (PDF)", type=["pdf"], accept_multiple_files=True)
        if uploaded_files:
            if not os.path.exists("data/resumes"):
                os.makedirs("data/resumes")

            for uploaded_file in uploaded_files:
                if uploaded_file.name not in st.session_state['resumes']:
                    # Save to local resumes folder
                    save_path = f"data/resumes/{uploaded_file.name}"
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    # Parse text
                    from job_hunter.resume_parser import parse_resume
                    text = parse_resume(save_path)

                    st.session_state['resumes'][uploaded_file.name] = {
                        "filename": uploaded_file.name,
                        "file_path": os.path.abspath(save_path),
                        "text": text,
                        "target_keywords": ""
                    }
                    db.save_resume_config(st.session_state['resumes'])
                    st.success(f"Uploaded {uploaded_file.name}")

    with col_list:
        if st.session_state['resumes']:
            for name, data in list(st.session_state['resumes'].items()):
                c1, c2 = st.columns([4, 1])
                c1.info(f"📋 **{name}**")
                if c2.button("🗑️", key=f"del_{name}"):
                    del st.session_state['resumes'][name]
                    db.save_resume_config(st.session_state['resumes'])
                    st.rerun()

                # Load History for this resume
                history = db.load_resume_title_history(name)

                # Target Keywords for this resume
                kw = st.text_input(f"Target Keywords for {name} (separate by ';')",
                                   value=data.get('target_keywords', ""),
                                   key=f"kw_{name}",
                                   placeholder="e.g. Data Scientist; Machine Learning Engineer")

                if history:
                    st.caption(f"Recent: {', '.join(history[:5])}")
                    if st.button(f"Load Previous Keywords ({name})", key=f"btn_prev_{name}"):
                        st.session_state['resumes'][name]['target_keywords'] = "; ".join(history)
                        db.save_resume_config(st.session_state['resumes'])
                        st.rerun()

                if kw != data.get('target_keywords'):
                    st.session_state['resumes'][name]['target_keywords'] = kw
                    db.save_resume_config(st.session_state['resumes'])
        else:
            st.info("No resumes uploaded yet.")

    st.divider()

    # --- 2. MISSION SETUP ---
    st.subheader("🛰️ Mission Setup")

    col1, col2 = st.columns(2)
    with col1:
        scrape_location = st.text_input("Target Locations (separate by ';')", value="Germany; Remote", help="e.g. Berlin; London; Remote")
        scrape_limit = st.slider("Max jobs per keyword per platform", 5, 50, 15)
        selected_platforms = st.multiselect("Target Platforms", ["LinkedIn", "Indeed", "Xing", "Stepstone", "ZipRecruiter"], default=["LinkedIn", "Indeed", "Xing"])

    with col2:
        mode = st.radio("🚀 Execution Mode:", ["✨ Easy Apply Live (Scout + Apply Now)", "🔍 Deep Scrape (Scout + Detailed JD + AI Analysis)"], index=1)

        st.markdown("---")
        # Global AI Analysis Toggle
        use_browser_analysis = st.toggle("🌐 Use Browser-based AI Analysis (ChatGPT/Gemini)", value=True, help="If OFF, will try to use Gemini API (Redundant if you want to save API costs).")

        if mode.startswith("🔍"):
            deep_scrape_toggle = st.checkbox("Fetch Complete Details (integrated)", value=True, help="Slows down scouting but gathers full JD for AI Analysis immediately.")
        else:
            deep_scrape_toggle = False

    st.divider()

    # --- 3. LAUNCH ---
    col_launch, col_skip = st.columns([2, 1])

    with col_launch:
        if st.button("🚀 Launch All Missions", type="primary", use_container_width=True, disabled=not st.session_state['resumes']):
            from job_hunter.mission_manager import MissionManager
            mm = MissionManager(db)

            with st.status("🚀 Launching Missions...", expanded=True) as status_box:
                if mode.startswith("✨"):
                    # LIVE APPLY MODE
                    mm.run_live_apply_mission(
                        resumes=st.session_state['resumes'],
                        locations=scrape_location,
                        limit=scrape_limit,
                        platforms=selected_platforms,
                        status_box=status_box
                    )
                else:
                    # STANDARD SCRAPE MODE
                    mm.run_standard_scrape_mission(
                        resumes=st.session_state['resumes'],
                        locations=scrape_location,
                        limit=scrape_limit,
                        platforms=selected_platforms,
                        deep_scrape=deep_scrape_toggle,
                        use_browser_analysis=use_browser_analysis,
                        status_box=status_box
                    )

            st.cache_data.clear()
            st.session_state['page'] = 'explorer'
            time.sleep(1)
            st.rerun()

    with col_skip:
         if st.button("📂 Load Existing Jobs (Skip Scrape)", use_container_width=True):
             st.cache_data.clear()
             st.session_state['page'] = 'explorer'
             st.rerun()
