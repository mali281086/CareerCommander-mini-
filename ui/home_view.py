import streamlit as st
import time
import os

def render_home_view(db):
    st.title("🚀 CareerCommander (Mini)")
    st.markdown("Automate your job search across LinkedIn, Indeed, Xing, and more.")

    # --- 1. RESUME MANAGEMENT ---
    st.subheader("📄 Resume Management")

    # Process uploads at the top of the section
    uploaded_files = st.file_uploader("Upload Resumes (PDF)", type=["pdf"], accept_multiple_files=True, key="resume_uploader")

    if uploaded_files:
        if not os.path.exists("data/resumes"):
            os.makedirs("data/resumes")

        new_upload = False
        # Only show spinner if there are actually new files to process
        needs_processing = any(f.name not in st.session_state['resumes'] for f in uploaded_files)

        if needs_processing:
            with st.spinner("Processing new resumes..."):
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
                            "pdf_bytes": uploaded_file.getvalue(),
                            "target_keywords": ""
                        }
                        new_upload = True

                if new_upload:
                    db.save_resume_config(st.session_state['resumes'])
                    st.toast("✅ Resumes processed!")
                    st.rerun()

    st.divider()

    # --- 2. CONFIGURATION COLUMNS ---
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("### 🤖 AI Assistance")
        if st.session_state['resumes']:
            if st.button("Seek AI Suggested Job Titles", use_container_width=True, help="AI will analyze your resumes to suggest suitable job titles."):
                from job_hunter.career_advisor import CareerAdvisor
                # Optimized: Instantiate once to reuse the browser session
                advisor = CareerAdvisor()

                with st.spinner("AI is analyzing your resumes..."):
                    for name, data in st.session_state['resumes'].items():
                        suggestions = advisor.suggest_roles(data.get('text', ''))
                        if suggestions:
                            kw_str = "; ".join(suggestions)
                            st.session_state['resumes'][name]['target_keywords'] = kw_str
                            # Also update the widget's state if it exists to ensure UI reflects change
                            st.session_state[f"kw_{name}"] = kw_str

                    advisor.close()
                    db.save_resume_config(st.session_state['resumes'])
                    st.success("✅ AI suggestions applied!")
                    st.rerun()
            st.caption("Let AI suggest job titles that fit your background.")
        else:
            st.info("It is better to upload all the resumes before seeking suggestions.")

    with col_right:
        st.markdown("### 🎯 Target Roles & Keywords")
        if st.session_state['resumes']:
            for name, data in list(st.session_state['resumes'].items()):
                with st.expander(f"📋 {name}", expanded=True):
                    c1, c2 = st.columns([4, 1])
                    # Target Keywords for this resume
                    kw = c1.text_input("Job Titles (separate by ';')",
                                       value=data.get('target_keywords', ""),
                                       key=f"kw_{name}",
                                       placeholder="e.g. Data Scientist; Machine Learning Engineer")

                    if c2.button("🗑️", key=f"del_{name}", help="Remove Resume"):
                        del st.session_state['resumes'][name]
                        db.save_resume_config(st.session_state['resumes'])
                        st.rerun()

                    # Load History for this resume
                    history = db.load_resume_title_history(name)
                    if history:
                        st.caption(f"Recent: {', '.join(history[:3])}...")
                        if st.button(f"🔄 Load History", key=f"btn_prev_{name}", use_container_width=True):
                            kw_str = "; ".join(history)
                            st.session_state['resumes'][name]['target_keywords'] = kw_str
                            # Also update the widget's state
                            st.session_state[f"kw_{name}"] = kw_str
                            db.save_resume_config(st.session_state['resumes'])
                            st.rerun()

                    if kw != data.get('target_keywords'):
                        st.session_state['resumes'][name]['target_keywords'] = kw
                        db.save_resume_config(st.session_state['resumes'])
        else:
            st.info("No resumes configured. Upload a PDF to start.")

    st.divider()

    # --- 3. MISSION SETUP ---
    st.subheader("🛰️ Mission Setup")

    m_col1, m_col2 = st.columns(2)
    with m_col1:
        scrape_location = st.text_input("Target Locations (separate by ';')", value="Germany; Remote", help="e.g. Berlin; London; Remote")
        scrape_limit = st.slider("Max jobs per keyword per platform", 5, 50, 15)
        selected_platforms = st.multiselect("Target Platforms", ["LinkedIn", "Indeed", "Xing", "Stepstone", "ZipRecruiter"], default=["LinkedIn", "Indeed", "Xing"])

    with m_col2:
        mode = st.radio("🚀 Execution Mode:", ["✨ Easy Apply Live (Scout + Apply Now)", "🔍 Deep Scrape (Scout + Detailed JD + AI Analysis)"], index=1)

        st.markdown("---")
        # Global AI Analysis Toggle
        use_browser_analysis = st.toggle("🌐 Use Browser-based AI Analysis (ChatGPT/Gemini)", value=True)

        if mode.startswith("🔍"):
            deep_scrape_toggle = st.checkbox("Fetch Complete Details (integrated)", value=True)
        else:
            deep_scrape_toggle = False

    st.divider()

    # --- 4. LAUNCH ---
    col_launch, col_skip = st.columns([2, 1])

    with col_launch:
        if st.button("🚀 Launch All Missions", type="primary", use_container_width=True, disabled=not st.session_state['resumes']):
            from job_hunter.mission_manager import MissionManager
            mm = MissionManager(db)

            with st.status("🚀 Launching Missions...", expanded=True) as status_box:
                if mode.startswith("✨"):
                    mm.run_live_apply_mission(
                        resumes=st.session_state['resumes'],
                        locations=scrape_location,
                        limit=scrape_limit,
                        platforms=selected_platforms,
                        status_box=status_box
                    )
                else:
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
         if st.button("📂 View Existing Results", use_container_width=True):
             st.cache_data.clear()
             st.session_state['page'] = 'explorer'
             st.rerun()
