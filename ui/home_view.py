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

    if st.session_state.get('active_gemini_key_alias', "Select Key...") == "Select Key...":
        st.info("👈 **Start Here**: Please select (or add) a Google Gemini API Key in the sidebar.")
        st.stop()

    # 1. PROFILE SECTION
    with st.expander("📂 Step 1: Manage Resumes & Roles", expanded=not bool(st.session_state['resumes'])):
        uploaded_files = st.file_uploader("Upload Resumes (PDF)", type=["pdf"], accept_multiple_files=True)

        if uploaded_files:
            for up_file in uploaded_files:
                already_exists = any(d['filename'] == up_file.name for d in st.session_state['resumes'].values())
                if not already_exists:
                    with st.spinner(f"Processing {up_file.name}..."):
                        save_path = os.path.join("data", "resumes", up_file.name)
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                        with open(save_path, "wb") as f: f.write(up_file.getbuffer())
                        text = parse_resume(up_file)
                        if text:
                            role_key = up_file.name
                            st.session_state['resumes'][role_key] = {
                                "filename": up_file.name,
                                "file_path": save_path,
                                "text": text,
                                "bytes": up_file.getvalue(),
                                "target_keywords": ""
                            }
                            db.save_resume_config(st.session_state['resumes'])
                            st.toast(f"Added: {role_key}")

        if st.session_state['resumes']:
            st.write("### 🦸 Active Personas")
            roles = list(st.session_state['resumes'].keys())
            cols = st.columns(3)
            for i, role_key in enumerate(roles):
                data = st.session_state['resumes'][role_key]
                with cols[i % 3]:
                    with st.container(border=True):
                        st.caption(f"📄 {data['filename']}")
                        new_role_name = st.text_input("Persona Name", value=role_key, key=f"edit_{role_key}")
                        new_kw = st.text_area("Target Role(s) (';')", value=data.get('target_keywords', ''), key=f"kw_{role_key}")

                        if new_kw != data.get('target_keywords'):
                            st.session_state['resumes'][role_key]['target_keywords'] = new_kw
                            db.save_resume_config(st.session_state['resumes'])

                        if new_role_name != role_key:
                            st.session_state['resumes'][new_role_name] = st.session_state['resumes'].pop(role_key)
                            db.save_resume_config(st.session_state['resumes'])
                            st.rerun()

                        c1, c2 = st.columns(2)
                        if c1.button("📜 Load Previous", key=f"prev_{role_key}"):
                            prev = db.load_resume_title_history(data['filename'])
                            if prev:
                                st.session_state['resumes'][role_key]['target_keywords'] = "; ".join(prev)
                                db.save_resume_config(st.session_state['resumes'])
                                st.rerun()
                        if c2.button("🗑️ Remove", key=f"del_{role_key}"):
                            del st.session_state['resumes'][role_key]
                            db.save_resume_config(st.session_state['resumes'])
                            st.rerun()

    # 2. MISSION CONFIG
    st.divider()
    st.subheader("Step 2: Mission Configuration")

    with st.container(border=True):
        if not st.session_state['resumes']:
            st.warning("⚠️ Please upload a resume first.")
        else:
            c1, c2 = st.columns(2)
            scrape_location = c1.text_input("Target Location(s)", value=st.session_state.get('scrape_location', "Germany"))
            st.session_state['scrape_location'] = scrape_location
            scrape_limit = c2.number_input("Limit per Role", value=30, min_value=1)

            c_easy, c_deep = st.columns(2)
            easy_apply_live = c_easy.toggle("✨ Easy Apply Live", value=False)
            deep_scrape = c_deep.toggle("🕵️ Deep Scrape JDs", value=True)

            platforms = ["LinkedIn", "Indeed", "Stepstone", "Xing", "ZipRecruiter"]
            selected_platforms = st.multiselect("Platforms", platforms, default=["LinkedIn", "Indeed", "Xing"])

            if st.button("🚀 Launch All Missions", type="primary", use_container_width=True, disabled=not st.session_state['resumes']):
                status_box = st.empty()
                manager = MissionManager(db)
                if easy_apply_live:
                    applied, skipped, errors, unknown = manager.run_live_apply(
                        st.session_state['resumes'], scrape_location, scrape_limit, selected_platforms,
                        st.session_state.get('use_browser_analysis', True), status_box
                    )
                else:
                    manager.run_standard_scrape(
                        st.session_state['resumes'], scrape_location, scrape_limit, selected_platforms,
                        deep_scrape, st.session_state.get('use_browser_analysis', True), status_box
                    )
                st.cache_data.clear()
                navigate_to('explorer')

            if st.button("📂 Load Previous Results (Skip Scrape)", use_container_width=True):
                st.cache_data.clear()
                navigate_to('explorer')
