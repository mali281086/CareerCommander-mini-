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
        # Easy Apply Batch
        apply_platforms = ["LinkedIn", "Xing", "Indeed"]
        eligible_for_easy = filtered[filtered["Easy Apply"] & (filtered["Status"] == "") & filtered["Platform"].isin(apply_platforms)]
        eligible_count = len(eligible_for_easy)

        if st.button(f"🤖 Easy Apply Batch ({eligible_count})", type="primary", use_container_width=True, disabled=(eligible_count == 0)):
            st.session_state['show_easy_apply_confirm'] = True

    # --- DATA GRID ---
    st.subheader(f"Results ({len(filtered)})")

    # Sort by Platform, then Title
    filtered = filtered.sort_values(by=["Platform", "Job Title"])

    # We'll use a manual loop to show jobs because we need custom buttons
    for idx, row in filtered.iterrows():
        job_id = f"{row['Job Title']}-{row['Company']}"
        is_applied = (row["Status"] != "")

        with st.container():
            c1, c2, c3, c4, c5 = st.columns([3, 2, 1, 1, 2])

            c1.markdown(f"**{row['Job Title']}**")
            c1.caption(f"{row['Company']} | {row['Platform']} | {row['Language']}")

            if row['Easy Apply']:
                c2.markdown("✨ **Easy Apply**")
            else:
                c2.markdown("Standard")

            c3.markdown(row["Status"])

            # Action buttons
            with c5:
                act_cols = st.columns(4)
                if act_cols[0].button("📝", key=f"intel_{job_id}_{idx}", help="Analyze"):
                    st.session_state['selected_job_for_analysis'] = row.to_dict()
                    st.session_state['show_analysis_panel'] = True

                if act_cols[1].button("✅", key=f"mark_{job_id}_{idx}", help="Mark as Applied"):
                    st.session_state['applied_jobs'] = db.save_applied(job_id, row.to_dict(), status="applied")
                    db.archive_applied_jobs()
                    st.toast(f"Marked {row['Job Title']} as Applied!")
                    st.rerun()

                if act_cols[2].button("🅿️", key=f"park_{job_id}_{idx}", help="Park (Hide)"):
                    db.park_job(row['Job Title'], row['Company'], row.to_dict())
                    st.rerun()

                if act_cols[3].button("🗑️", key=f"del_{job_id}_{idx}", help="Delete"):
                    db.delete_scouted_job(row['Job Title'], row['Company'])
                    st.rerun()

    # --- ANALYSIS PANEL ---
    if st.session_state.get('show_analysis_panel', False):
        job = st.session_state['selected_job_for_analysis']
        render_analysis_panel(job, db)

    # --- CONFIRMATION DIALOG (Easy Apply Batch) ---
    if st.session_state.get('show_easy_apply_confirm', False):
        render_easy_apply_confirm(eligible_for_easy, db)

    # --- METRICS ---
    st.markdown("---")
    with st.expander("📈 Metrics and Visualisations", expanded=False):
        render_metrics_dashboard(df_display, st.session_state['applied_jobs'], len(db.load_parked()))

def render_analysis_panel(job, db):
    job_id = f"{job['Job Title']}-{job['Company']}"
    st.markdown("---")
    st.subheader(f"🧠 AI Analysis: {job['Job Title']} @ {job['Company']}")

    if st.button("❌ Close Analysis Panel"):
        st.session_state['show_analysis_panel'] = False
        st.rerun()

    # Analysis logic (similar to app.py)
    # Check if in cache
    cache = db.load_cache()
    is_analyzed = job_id in cache
    analysis_results = cache.get(job_id, {})

    # Resume Selection for analysis
    resume_options = list(st.session_state.get('resumes', {}).keys())
    selected_resume_key = st.selectbox("Analyze with Resume:", resume_options, key="analyze_resume_sel")
    selected_resume_data = st.session_state['resumes'].get(selected_resume_key, {})

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
        render_chat_tab(job, selected_resume_data, analysis_results, db)

def render_chat_tab(job, resume_data, analysis_results, db):
    job_id = f"{job['Job Title']}-{job['Company']}"

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
                browser_llm = BrowserLLM(provider="ChatGPT", headless=True)

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

def render_easy_apply_confirm(eligible_jobs, db):
    st.warning("⚠️ **Confirmation Required**")
    count = len(eligible_jobs)
    st.markdown(f"**Are you sure you want to start Easy Apply for {count} jobs?**")

    resume_options = list(st.session_state.get('resumes', {}).keys())
    easy_resume_key = st.selectbox("Select Resume", resume_options)
    easy_resume_path = st.session_state['resumes'].get(easy_resume_key, {}).get('file_path', '')
    easy_phone = st.text_input("Phone Number (optional)", value="+49 176 26983236")

    c1, c2 = st.columns(2)
    if c1.button("✅ Confirm Auto-Apply", type="primary"):
        st.session_state['show_easy_apply_confirm'] = False

        from job_hunter.mission_manager import MissionManager
        mm = MissionManager(db)

        status_box = st.empty()
        # Fill NaN values to avoid crashes in mission manager
        jobs_list = eligible_jobs.fillna("").to_dict('records')

        with st.spinner("Executing Batch Apply..."):
            mm.run_batch_apply_mission(
                eligible_jobs=jobs_list,
                resume_path=easy_resume_path,
                phone_number=easy_phone,
                status_box=status_box
            )

        st.success("🎉 Batch Apply Complete!")
        st.rerun()

    if c2.button("❌ Cancel"):
        st.session_state['show_easy_apply_confirm'] = False
        st.rerun()
