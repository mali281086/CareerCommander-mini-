import streamlit as st
import pandas as pd
import base64
from ui.metrics import render_metrics_dashboard
from job_hunter.analysis_crew import JobAnalysisCrew

def render_explorer_view(db):
    st.title("🔎 Mission Results")

    # Load data
    scouted_jobs = db.load_scouted()
    if not scouted_jobs:
        st.warning("No data found. Please go back and run a search.")
        return

    # Initialize selection state
    if 'selected_jobs' not in st.session_state:
        st.session_state['selected_jobs'] = set()

    # Convert to DataFrame for easier handling
    df = pd.DataFrame(scouted_jobs)
    # Ensure columns exist
    for col in ['title', 'company', 'platform', 'location', 'link', 'is_easy_apply', 'language', 'rich_description']:
        if col not in df.columns: df[col] = ""

    # Map internal keys to display labels
    df_display = df.rename(columns={
        'title': 'Job Title',
        'company': 'Company',
        'platform': 'Platform',
        'location': 'Location',
        'is_easy_apply': 'Easy Apply',
        'language': 'Language'
    })

    # --- BLACKLIST MANAGER ---
    with st.expander("🚫 Blacklist Manager (Quick Block)", expanded=False):
         bl_data = db.load_blacklist()
         bl_companies_str = "; ".join(bl_data.get("companies", []))
         bl_titles_str = "; ".join(bl_data.get("titles", []))
         bl_safe_str = "; ".join(bl_data.get("safe_phrases", []))

         st.caption(f"Add companies or titles here to drop them. SAFE PHRASES will rescue a job if it contains a blacklisted title word.\n\nUse ';' to separate multiple entries.")

         c_bl1, c_bl2, c_bl3 = st.columns(3)
         new_companies = c_bl1.text_area("Block Companies", value=bl_companies_str, help="e.g. BadCorp; Boring Ltd", key="bl_comp_mgr")
         new_titles = c_bl2.text_area("Block Job Titles", value=bl_titles_str, help="e.g. Intern; Unpaid", key="bl_title_mgr")
         new_safe = c_bl3.text_area("Safe Phrases (Rescue)", value=bl_safe_str, help="e.g. Analyst; Manager", key="bl_safe_mgr")

         if st.button("Save Updates", key="btn_save_bl"):
             c_list = [c.strip() for c in new_companies.split(';') if c.strip()]
             t_list = [t.strip() for t in new_titles.split(';') if t.strip()]
             s_list = [s.strip() for s in new_safe.split(';') if s.strip()]
             db.save_blacklist(c_list, t_list, s_list)
             st.toast("Blacklist Updated! 🛡️")

    # Status helper
    def get_status(row):
        jid = f"{row['Job Title']}-{row['Company']}"
        if jid in st.session_state['applied_jobs']: return "✅ Applied"
        return ""
    df_display["Status"] = df_display.apply(get_status, axis=1)

    # --- FILTERS ---
    st.sidebar.subheader("🎯 Filter Results")
    platforms = ["All"] + sorted(df_display["Platform"].unique().tolist())
    sel_platform = st.sidebar.selectbox("Platform", platforms)

    languages = ["All"] + sorted(df_display["Language"].unique().tolist())
    sel_lang = st.sidebar.selectbox("Language", languages)

    easy_only = st.sidebar.checkbox("Easy Apply Only", value=False)
    hide_applied = st.sidebar.checkbox("Hide Applied", value=True)

    # Apply Filters
    filtered = df_display.copy()
    if sel_platform != "All": filtered = filtered[filtered["Platform"] == sel_platform]
    if sel_lang != "All": filtered = filtered[filtered["Language"] == sel_lang]
    if easy_only: filtered = filtered[filtered["Easy Apply"] == True]
    if hide_applied: filtered = filtered[filtered["Status"] == ""]

    # --- ACTIONS ---
    st.markdown("---")
    c_act1, c_act2, c_act3, c_act4 = st.columns([1, 1, 1, 1])

    with c_act1:
        if st.button("🏁 End Day / Archive Applied", use_container_width=True):
            removed = db.archive_applied_jobs()
            st.toast(f"Archived {removed} jobs.")
            st.rerun()

    with c_act2:
        if st.button("🅿️ Park Language", use_container_width=True):
            if sel_lang != "All":
                to_park = filtered[filtered["Language"] == sel_lang]
                for idx, row in to_park.iterrows():
                    db.park_job(row['Job Title'], row['Company'], row.to_dict())
                st.toast(f"Parked {len(to_park)} {sel_lang} jobs.")
                st.rerun()
            else:
                st.warning("Select a specific language first.")

    with c_act3:
        selected_count = len(st.session_state['selected_jobs'])
        btn_label = f"🚀 Apply Selected ({selected_count})"
        if st.button(btn_label, type="primary", use_container_width=True, disabled=(selected_count == 0)):
            # Filter specifically selected jobs
            selected_df = filtered[filtered.apply(lambda r: f"{r['Job Title']}-{r['Company']}" in st.session_state['selected_jobs'], axis=1)]
            render_vision_apply_confirm(selected_df, db)

    with c_act4:
        selected_count = len(st.session_state['selected_jobs'])
        btn_label = f"🧠 Batch AI Analysis ({selected_count})" if selected_count > 0 else "🧠 Batch AI Analysis"
        if st.button(btn_label, type="secondary", use_container_width=True, disabled=(selected_count == 0)):
            # Filter specifically selected jobs
            selected_df = filtered[filtered.apply(lambda r: f"{r['Job Title']}-{r['Company']}" in st.session_state['selected_jobs'], axis=1)]
            render_batch_analysis_confirm(selected_df, db)

    # --- DATA GRID ---
    st.markdown("---")
    st.subheader(f"Results ({len(filtered)})")

    # Selection Helpers
    c_sel1, c_sel2, c_sel3 = st.columns([1, 1, 4])
    if c_sel1.button("✅ Select All Filtered", use_container_width=True):
        for idx, row in filtered.iterrows():
            st.session_state['selected_jobs'].add(f"{row['Job Title']}-{row['Company']}")
        st.rerun()
    if c_sel2.button("🚫 Clear Selection", use_container_width=True):
        st.session_state['selected_jobs'] = set()
        st.rerun()

    # Sort by Platform, then Title
    filtered = filtered.sort_values(by=["Platform", "Job Title"])

    # We'll use a manual loop to show jobs because we need custom buttons
    for idx, row in filtered.iterrows():
        job_id = f"{row['Job Title']}-{row['Company']}"
        is_applied = (row["Status"] != "")
        is_selected = job_id in st.session_state['selected_jobs']

        with st.container():
            # Adjusted columns to include checkbox
            c_sel, c1, c2, c3, c4, c5 = st.columns([0.3, 3, 2, 1, 1, 2.5])

            # Checkbox for selection
            if c_sel.checkbox(" ", key=f"sel_{job_id}_{idx}", value=is_selected):
                if not is_selected:
                    st.session_state['selected_jobs'].add(job_id)
                    st.rerun()
            else:
                if is_selected:
                    st.session_state['selected_jobs'].remove(job_id)
                    st.rerun()

            if row.get('link'):
                c1.markdown(f"**[{row['Job Title']}]({row['link']})**")
            else:
                c1.markdown(f"**{row['Job Title']}**")
                
            c1.caption(f"{row['Company']} | {row['Platform']} | {row['Language']}")

            if row['Easy Apply']:
                c2.markdown("✨ **Easy Apply**")
            else:
                c2.markdown("Standard")

            c3.markdown(row["Status"])

            # Action buttons
            with c5:
                act_cols = st.columns(6)
                
                if act_cols[0].button("🚀", key=f"apply_{job_id}_{idx}", help="Apply via Vision API"):
                    # Launch single job confirm/direct
                    render_vision_apply_confirm(pd.DataFrame([row]), db)
                
                if row.get('link'):
                    act_cols[1].link_button("🔗", row['link'], help="Open Job Link")
                else:
                    act_cols[1].button("🔗", disabled=True, key=f"nolink_{job_id}_{idx}")
                
                if act_cols[2].button("📝", key=f"intel_{job_id}_{idx}", help="Analyze"):
                    render_analysis_dialog(row.to_dict(), db)
                
                if act_cols[3].button("✅", key=f"mark_{job_id}_{idx}", help="Mark as Applied"):
                    st.session_state['applied_jobs'] = db.save_applied(job_id, row.to_dict(), status="applied")
                    db.archive_applied_jobs()
                    st.toast(f"Marked {row['Job Title']} as Applied!")
                    st.rerun()

                if act_cols[4].button("🅿️", key=f"park_{job_id}_{idx}", help="Park (Hide)"):
                    db.park_job(row['Job Title'], row['Company'], row.to_dict())
                    st.rerun()

                if act_cols[5].button("🗑️", key=f"del_{job_id}_{idx}", help="Delete"):
                    db.delete_scouted_job(row['Job Title'], row['Company'])
                    st.rerun()

    # --- CONFIRMATION DIALOG (Easy Apply Batch) ---
    # Dialog is now opened directly via button click above

    # --- METRICS ---
    st.markdown("---")
    with st.expander("📈 Metrics and Visualisations", expanded=False):
        render_metrics_dashboard(df_display, st.session_state['applied_jobs'], len(db.load_parked()))

@st.dialog("🧠 Job Analysis", width="large")
def render_analysis_dialog(job, db):
    st.subheader(f"{job['Job Title']} @ {job['Company']}")

    # Resume Selection for analysis (Must be before job_id calc for resume-awareness)
    resume_options = list(st.session_state.get('resumes', {}).keys())
    selected_resume_key = st.selectbox("Analyze with Resume:", resume_options, key="analyze_resume_sel")
    selected_resume_data = st.session_state['resumes'].get(selected_resume_key, {})

    # Analysis logic (Resume-aware)
    job_id = db.generate_job_id(job['Job Title'], job['Company'], selected_resume_key)

    # Check if in cache
    cache = db.load_cache()
    is_analyzed = job_id in cache
    analysis_results = cache.get(job_id, {})

    if st.button("🤖 Run/Refresh AI Analysis", type="primary"):
        if not selected_resume_data:
            st.error("Please upload and select a resume first.")
        else:
            with st.spinner("Analyzing with AI..."):
                jd = job.get('rich_description') or job.get('Job Description') or ""
                context = f"Title: {job['Job Title']}\nCompany: {job['Company']}\nJD: {jd}"

                crew = JobAnalysisCrew(context, selected_resume_data['text'])
                # Hardcoded use_browser=True as per optimization goals
                results = crew.run_analysis(use_browser=True)

                if results and "error" not in results:
                    db.save_cache(job_id, results)
                    st.session_state['job_cache'][job_id] = results
                    st.success("Analysis Complete!")
                    st.rerun()
                else:
                    st.error(f"Analysis failed: {results.get('error', 'Unknown error')}")

    # Tabs for results
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["💡 Intel", "📝 Cover Letter", "🎯 ATS Match", "📄 Strategized Resume", "💬 Ask AI"])

    with tab1:
        if not is_analyzed: st.info("Run AI Analysis first.")
        else:
            intel = analysis_results.get("company_intel", {})
            st.write(f"**Mission**: {intel.get('mission', 'N/A')}")
            st.write(f"**HQ**: {intel.get('headquarters', 'N/A')}")
            st.write(f"**Employees**: {intel.get('employees', 'N/A')}")
            st.write("**Key Facts**:")
            for f in intel.get('key_facts', []): st.markdown(f"• {f}")

    with tab2:
        if not is_analyzed: st.info("Run AI Analysis first.")
        else:
            st.write(f"**Humanization Level:** {analysis_results.get('humanization_score', 0)}%")
            st.text_area("Cover Letter", analysis_results.get("cover_letter", ""), height=400)

    with tab3:
        if not is_analyzed: st.info("Run AI Analysis first.")
        else:
            ats = analysis_results.get("ats_report", {})
            st.metric("Match Score", f"{ats.get('score', 0)}%")
            st.write("**Missing Skills:**")
            for s in ats.get("missing_skills", []): st.caption(f"❌ {s}")

    with tab4:
        if not is_analyzed: st.info("Run AI Analysis first.")
        else:
            c_res1, c_res2 = st.columns([1, 1])
            with c_res1:
                st.text_area("Tailored Resume", analysis_results.get("tailored_resume", ""), height=600)
            with c_res2:
                st.markdown("### Original Resume Preview")
                if "pdf_bytes" in selected_resume_data:
                    base64_pdf = base64.b64encode(selected_resume_data['pdf_bytes']).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                else:
                    st.warning("PDF bytes not found in session. Try re-uploading.")

    with tab5:
        render_chat_tab(job, selected_resume_key, selected_resume_data, analysis_results, db)

def render_chat_tab(job, resume_name, resume_data, analysis_results, db):
    job_id = db.generate_job_id(job['Job Title'], job['Company'], resume_name)

    c_chat1, c_chat2 = st.columns([1, 1])

    with c_chat2:
        st.markdown("### Resume Preview")
        if "pdf_bytes" in resume_data:
            base64_pdf = base64.b64encode(resume_data['pdf_bytes']).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)

    with c_chat1:
        st.subheader("💬 Ask AI")
    if "chat_history" not in st.session_state: st.session_state.chat_history = {}
    if job_id not in st.session_state.chat_history:
        st.session_state.chat_history[job_id] = analysis_results.get("qna_history", [])

    for msg in st.session_state.chat_history[job_id]:
        with st.chat_message(msg["role"]): st.write(msg["content"])

    if user_query := st.chat_input("Ask about this job...", key=f"chat_input_{job_id}"):
        st.session_state.chat_history[job_id].append({"role": "user", "content": user_query})
        with st.chat_message("user"): st.write(user_query)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Use BrowserLLM for chat if API is removed
                from tools.browser_llm import BrowserLLM

                bot_config = db.load_bot_config()
                headless = bot_config.get("settings", {}).get("ai_headless", True)

                browser_llm = BrowserLLM(provider="ChatGPT", headless=headless)

                jd = job.get('rich_description') or job.get('Job Description') or ""
                context = f"Job: {job['Job Title']} at {job['Company']}\nJD: {jd}\nResume: {resume_data.get('text', '')}"
                prompt = f"Context:\n{context}\n\nQuestion: {user_query}\nAnswer in 2-3 sentences max."

                response = browser_llm.ask(prompt)
                st.write(response)
                browser_llm.close_tab()

                st.session_state.chat_history[job_id].append({"role": "assistant", "content": response})
                # Save to cache
                if job_id not in st.session_state['job_cache']: st.session_state['job_cache'][job_id] = {}
                st.session_state['job_cache'][job_id]['qna_history'] = st.session_state.chat_history[job_id]
                db.save_cache(job_id, st.session_state['job_cache'][job_id])
                st.rerun()

@st.dialog("🚀 Confirm Vision Batch Apply")
def render_vision_apply_confirm(eligible_jobs, db):
    st.info("🚀 **Vision-Based Application**")
    count = len(eligible_jobs)
    st.markdown(f"**Are you sure you want to launch the Vision Applier for {count} jobs?**")
    st.caption("The bot will navigate, analyze screenshots, and fill forms automatically.")

    # Build mapping for auto-selection in the background
    resume_mapping = { name: data.get('file_path') for name, data in st.session_state.get('resumes', {}).items() }
    
    # Use the first resume path as a system default if a job has no tag
    default_path = list(resume_mapping.values())[0] if resume_mapping else ""

    easy_phone = st.text_input("Phone Number (optional)", value="+49 176 26983236")

    c1, c2 = st.columns(2)
    if c1.button("✅ Launch Vision Bot", type="primary"):
        from job_hunter.mission_manager import MissionManager
        mm = MissionManager(db)

        status_box = st.empty()
        # Fill NaN values to avoid crashes in mission manager
        jobs_list = eligible_jobs.fillna("").to_dict('records')

        with st.spinner("Vision Bot is working..."):
            mm.run_batch_apply_mission(
                eligible_jobs=jobs_list,
                resume_path=default_path,
                phone_number=easy_phone,
                status_box=status_box,
                resume_mapping=resume_mapping
            )

        st.success("🎉 Vision Batch Apply Complete!")
        st.rerun()

    if c2.button("❌ Cancel"):
        st.rerun()

@st.dialog("🧠 Confirm Batch Analysis")
def render_batch_analysis_confirm(jobs_to_analyze_df, db):
    resume_options = list(st.session_state.get('resumes', {}).keys())
    if not resume_options:
        st.warning("Please upload a resume first.")
        return
        
    selected_resume_key = st.selectbox("Analyze selected jobs with Resume:", resume_options)
    
    # Calculate how many are missing analysis
    cache = db.load_cache()
    missing_jobs = []
    
    for idx, row in jobs_to_analyze_df.iterrows():
        job_id = db.generate_job_id(row['Job Title'], row['Company'], selected_resume_key)
        # Include if not in cache OR if the cached result is an error
        if job_id not in cache or "error" in cache.get(job_id, {}):
            missing_jobs.append(row.to_dict())
            
    st.info(f"Out of the **{len(jobs_to_analyze_df)}** selected jobs, **{len(missing_jobs)}** are missing AI Analysis.")
    
    if len(missing_jobs) == 0:
        st.success("All jobs are already processed!")
        if st.button("Close"):
            st.rerun()
        return

    c1, c2 = st.columns(2)
    if c1.button("✅ Run Background Batch", type="primary"):
        resume_data = st.session_state['resumes'].get(selected_resume_key, {})
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        from job_hunter.analysis_crew import JobAnalysisCrew
        import time
        
        with st.spinner("Processing in background..."):
            for i, job in enumerate(missing_jobs):
                status_text.text(f"Analyzing: {job['Job Title']} at {job['Company']} ({i+1}/{len(missing_jobs)})...")
                jd = job.get('rich_description') or job.get('Job Description') or ""
                context = f"Title: {job['Job Title']}\nCompany: {job['Company']}\nJD: {jd}"

                crew = JobAnalysisCrew(context, resume_data['text'])
                # Pass close_after=False to keep session open during batch
                results = crew.run_analysis(use_browser=True, close_after=False)
                
                if results and "error" not in results:
                    job_id = db.generate_job_id(job['Job Title'], job['Company'], selected_resume_key)
                    db.save_cache(job_id, results)
                    st.session_state['job_cache'][job_id] = results
                else:
                    st.toast(f"Skipped {job['Company']} (Error). Keep monitoring.", icon="⚠️")
                
                progress_bar.progress((i + 1) / len(missing_jobs))
                time.sleep(1)  # Brief pause between jobs
            
            # Close browser when batch is fully done (only if we processed something)
            if missing_jobs:
                from tools.browser_llm import BrowserLLM
                bl = BrowserLLM(profile_name="llm_profile")
                bl.close_tab()
                
        st.success("Batch Analysis Complete!")
        if st.button("Finish & Refresh"):
            st.rerun()

    if c2.button("❌ Cancel"):
        st.rerun()

