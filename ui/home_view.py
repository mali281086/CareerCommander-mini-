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
                advisor = CareerAdvisor(db=db)

                with st.spinner("AI is analyzing your resumes..."):
                    success_count = 0
                    fail_count = 0
                    
                    for name, data in st.session_state['resumes'].items():
                        suggestions = advisor.suggest_roles(data.get('text', ''))
                        if suggestions:
                            kw_str = "; ".join(suggestions)
                            st.session_state['resumes'][name]['target_keywords'] = kw_str
                            # Also update the widget's state if it exists to ensure UI reflects change
                            st.session_state[f"kw_{name}"] = kw_str
                            success_count += 1
                        else:
                            fail_count += 1

                    advisor.close()
                    db.save_resume_config(st.session_state['resumes'])
                    
                    if success_count > 0:
                        st.success(f"✅ AI suggestions applied for {success_count} resume(s)!")
                    
                    if fail_count > 0:
                        st.warning(f"⚠️ AI analysis failed for {fail_count} resume(s).")
                        st.info("💡 Try logging in first using 'Bot Setup (Login)' or disable 'Headless AI Analysis' in Bot Settings.")
                    
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
                    # Load History for this resume (before widget to allow state updates)
                    history = db.load_resume_title_history(name)
                    if history:
                        st.caption(f"Recent: {', '.join(history[:3])}...")
                        if st.button(f"🔄 Load History", key=f"btn_prev_{name}", use_container_width=True):
                            kw_str = "; ".join(history)
                            st.session_state['resumes'][name]['target_keywords'] = kw_str
                            # Pre-set the widget value before it's created
                            st.session_state[f"kw_{name}"] = kw_str
                            db.save_resume_config(st.session_state['resumes'])
                            st.rerun()

                    # Target Keywords for this resume
                    kw = c1.text_input("Job Titles (separate by ';')",
                                       value=data.get('target_keywords', ""),
                                       key=f"kw_{name}",
                                       placeholder="e.g. Data Scientist; Machine Learning Engineer")

                    if c2.button("🗑️", key=f"del_{name}", help="Remove Resume"):
                        del st.session_state['resumes'][name]
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
    with m_col2:
        st.markdown("### ⚙️ Search Mode")
        mode_help = """
        **Easy Apply Live**: Optimized for speed. Finds and applies immediately (No AI).
        **Standard Scrape**: Fetches full Job Descriptions. You can then choose to run AI Analysis automatically or manually (Batch).
        """
        mode = st.radio("🚀 Execution Mode:", 
                        ["✨ Easy Apply Live (Scout + Apply Now)", 
                         "🔍 Standard Scrape (Fetch Jobs + Detailed JDs)"], 
                        index=1, key="execution_mode", help=mode_help)

        st.markdown("---")
        # Global AI Analysis Toggle - Renamed to match user request
        st.markdown("### 🧠 AI Analysis Strategy")
        ai_strategy = st.radio("Choose how AI should analyze jobs:",
                               ["🤖 Full Auto (Analyze every job immediately)",
                                "🗳️ Batch Mode (Manual - I will select jobs later)"],
                               index=0, key="ai_strategy_radio")
        
        use_browser_analysis = (ai_strategy.startswith("🤖"))

        if mode.startswith("🔍"):
            st.caption("Deep Scrape is required to fetch the full text needed for AI Analysis.")
            deep_scrape_toggle = st.checkbox("Fetch Complete Details (Integrated)", value=True, disabled=True)
        else:
            deep_scrape_toggle = False

    with m_col1:
        scrape_location = st.text_input("Target Locations (separate by ';')", value="Germany; Remote", help="e.g. Berlin; London; Remote")
        scrape_limit = st.number_input("Max jobs per keyword per platform", min_value=1, max_value=100, value=5, help="Specify how many jobs to fetch for each keyword on each selected platform.")

        all_platforms = ["LinkedIn", "Indeed", "Xing", "Stepstone", "ZipRecruiter"]
        is_easy_apply_live = mode.startswith("✨")

        if is_easy_apply_live:
            available_platforms = ["LinkedIn", "Indeed", "Xing"]
            selected_platforms = st.multiselect(
                "Target Platforms",
                available_platforms,
                default=["LinkedIn"],
                key="platforms_live",
                help="Select platforms for live searching and applying."
            )
        else:
            available_platforms = all_platforms
            selected_platforms = st.multiselect(
                "Target Platforms",
                available_platforms,
                default=["LinkedIn", "Indeed", "Xing"],
                key="platforms_standard"
            )

    st.divider()

    # --- 4. LAUNCH ---
    from job_hunter.mission_state import MissionProgress
    progress = MissionProgress.load()

    # Check if a mission is running to decide what to show
    # We avoid using st.empty() for the entire container to prevent white screen hangs
    if progress.is_active and (progress.scouting_backlog or progress.analysis_backlog):
        st.info(f"⏳ An incomplete mission (**{progress.mission_type}**) was found. You can resume it or start a new one.")
        if st.button("▶️ Resume Previous Mission", type="primary", use_container_width=True):
            from job_hunter.mission_manager import MissionManager
            mm = MissionManager(db)
            with st.status("🚀 Resuming Mission...", expanded=True) as status_box:
                mm.resume_mission(status_box)

            st.cache_data.clear()
            st.session_state['page'] = 'explorer'
            st.rerun()
        st.divider()

    col_launch, col_skip = st.columns([2, 1])

    with col_launch:
        if st.button("🚀 Launch New Mission", type="primary", use_container_width=True, disabled=not st.session_state['resumes']):
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
            # Mark the completion clearly to the user
            st.toast("✅ Mission Complete!", icon="🚀")
            time.sleep(1)
            st.rerun()

    with col_skip:
         if st.button("📂 View Existing Results", use_container_width=True):
             st.cache_data.clear()
             st.session_state['page'] = 'explorer'
             st.rerun()
