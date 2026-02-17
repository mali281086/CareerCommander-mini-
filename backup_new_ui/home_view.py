import streamlit as st
import os
import time
from job_hunter.data_manager import DataManager
from job_hunter.resume_parser import parse_resume
from job_hunter.mission_manager import MissionManager
from ui.utils import navigate_to

def render_home_view():
    st.title("🎖️ CareerCommander")
    db = DataManager()

    # Check AI Setup
    if st.session_state.get('active_gemini_key_alias') == "Select Key...":
        st.warning("⚠️ Please select or add a Gemini API Key in the sidebar to begin.")
        st.stop()

    # --- Step 1: Brain & Resume ---
    st.header("1️⃣ Brain & Resume")

    with st.expander("📄 Manage Resumes / Personas", expanded=not bool(st.session_state['resumes'])):
        uploaded_files = st.file_uploader("Upload Resumes (PDF)", type="pdf", accept_multiple_files=True)

        if uploaded_files:
            for uploaded_file in uploaded_files:
                role_name = uploaded_file.name.replace(".pdf", "").replace("Resume", "").strip()
                if role_name not in st.session_state['resumes']:
                    with st.spinner(f"Parsing {uploaded_file.name}..."):
                        text = parse_resume(uploaded_file)
                        if text:
                            # Save file
                            fpath = os.path.join("data", "resumes", uploaded_file.name)
                            with open(fpath, "wb") as f: f.write(uploaded_file.getbuffer())

                            st.session_state['resumes'][role_name] = {
                                "filename": uploaded_file.name,
                                "file_path": fpath,
                                "text": text,
                                "bytes": uploaded_file.getvalue(),
                                "target_keywords": role_name
                            }
                            st.success(f"Added Persona: {role_name}")
            # Global save
            db.save_resume_config(st.session_state['resumes'])

        if st.session_state['resumes']:
            st.subheader("Active Personas")
            for role in list(st.session_state['resumes'].keys()):
                col1, col2 = st.columns([4, 1])
                col1.write(f"🎯 **{role}** ({st.session_state['resumes'][role]['filename']})")
                if col2.button("🗑️", key=f"del_{role}"):
                    del st.session_state['resumes'][role]
                    db.save_resume_config(st.session_state['resumes'])
                    st.rerun()

    if not st.session_state['resumes']:
        st.info("Please upload at least one resume to continue.")
        st.stop()

    # --- Step 2: Target Keywords ---
    st.header("2️⃣ Target Keywords & Location")
    for role, data in st.session_state['resumes'].items():
        st.session_state['resumes'][role]['target_keywords'] = st.text_input(
            f"Keywords for {role} (semicolon separated)",
            value=data.get('target_keywords', role),
            key=f"kw_{role}"
        )

    col_loc, col_lim = st.columns(2)
    scrape_location = col_loc.text_input("📍 Location(s)", value=st.session_state.get('scrape_location', 'Germany'), help="e.g. Germany; Berlin; Remote")
    st.session_state['scrape_location'] = scrape_location
    scrape_limit = col_lim.number_input("🔢 Limit per Search", min_value=1, max_value=100, value=10)

    # Keyword history for quick load
    if st.session_state['resumes']:
        first_resume = list(st.session_state['resumes'].values())[0]['filename']
        history = db.load_resume_title_history(first_resume)
        if history:
            selected_history = st.multiselect("🕰️ Recently used keywords", history)
            if selected_history:
                # Update keywords for the first resume as a convenience
                first_role = list(st.session_state['resumes'].keys())[0]
                st.session_state['resumes'][first_role]['target_keywords'] = "; ".join(selected_history)
                # st.rerun() # Might be too aggressive, let the user decide

    # --- Step 3: Launch Missions ---
    st.header("3️⃣ Launch Missions")

    platforms = ["LinkedIn", "Indeed", "Stepstone", "Xing", "ZipRecruiter"]
    selected_platforms = st.multiselect("Select Platforms", platforms, default=["LinkedIn", "Indeed", "Xing"])

    deep_scrape = st.toggle("🕵️ Deep Dive (Extract Full Descriptions)", value=True)
    live_apply = st.toggle("⚡ Live Apply (Apply while scouting)", value=False)

    if st.button("🚀 Launch Missions", use_container_width=True, type="primary"):
        status_box = st.empty()
        manager = MissionManager(db)

        if live_apply:
            applied, skipped, errors, unknown = manager.run_live_apply(
                st.session_state['resumes'], scrape_location, scrape_limit, selected_platforms,
                st.session_state.get('use_browser_analysis', True), status_box
            )
            status_box.success(f"🎉 Live Apply Complete! Applied: {applied} | Skipped: {skipped} | Errors: {errors}")
        else:
            manager.run_standard_scrape(
                st.session_state['resumes'], scrape_location, scrape_limit, selected_platforms,
                deep_scrape, st.session_state.get('use_browser_analysis', True), status_box
            )
            status_box.success("🎉 Mission Complete! Results saved.")

        st.cache_data.clear()
        time.sleep(1)
        navigate_to('explorer')

    # --- Load Previous ---
    if st.button("📂 Load Previous Results (Skip Scrape)", use_container_width=True):
        st.cache_data.clear()
        navigate_to('explorer')
