import streamlit as st
import pandas as pd
import base64
from job_hunter.data_manager import DataManager
from tools.logger import logger
from tools.browser_manager import BrowserManager
from ui.metrics import render_metrics_dashboard
import os

def render_explorer_view(db):
    # Premium UI Styling for Buttons - FLASHY EDITION
    st.markdown("""
        <style>
        /* Container for buttons */
        div[data-testid="column"] button {
            border-radius: 8px !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            background: rgba(255, 255, 255, 0.05) !important;
            transition: all 0.3s ease !important;
            height: 36px !important;
            width: 36px !important;
            padding: 0 !important;
            font-size: 1.1rem !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 auto !important;
        }
        
        /* Hover Effects */
        div[data-testid="column"] button:hover {
            transform: translateY(-1px) !important;
            background: rgba(255, 255, 255, 0.15) !important;
            border-color: #ff4b4b !important;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2) !important;
        }

        /* Specific Glow Colors */
        div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(1) button:hover { border-color: #00d4ff !important; }
        div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(3) button:hover { border-color: #ffaa00 !important; }
        div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-child(8) button:hover { border-color: #ff0000 !important; }
        </style>
    """, unsafe_allow_html=True)

    st.title("🔎 Explorer / Scouted")

    # Load data
    scouted_jobs = db.load_scouted()
    if not scouted_jobs:
        st.info("No scouted jobs found. Go to 'Home' to launch a mission.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(scouted_jobs)
    
    # Initialize selection state
    if 'selected_jobs' not in st.session_state:
        st.session_state['selected_jobs'] = set()
    if 'applied_jobs' not in st.session_state:
        st.session_state['applied_jobs'] = [j['link'] for j in db.load_applied()]

    # Use all jobs without filtering as requested
    filtered = df

    # Quick Blacklist Config
    with st.expander("🚫 Quick Blacklist Config", expanded=False):
        st.caption("Logic: Jobs matching 'Blocked' are dropped UNLESS they contain a 'Safe Phrase'.")
        bl = db.load_blacklist()
        bl_titles_str = ", ".join(bl.get("titles", []))
        new_bl_titles = st.text_area("Blocked Keywords (e.g. Marketing, Sales):", value=bl_titles_str, help="Comma separated")
        bl_safe_str = ", ".join(bl.get("safe_phrases", []))
        new_bl_safe = st.text_area("Safe Phrases (e.g. Analyst, Analysis):", value=bl_safe_str, help="Comma separated")
        
        if st.button("Update Blacklist JSON"):
            updated_titles = [t.strip() for t in new_bl_titles.split(",") if t.strip()]
            updated_safe = [s.strip() for s in new_bl_safe.split(",") if s.strip()]
            db.save_blacklist(bl.get("companies", []), updated_titles, updated_safe)
            st.toast("✅ Blacklist JSON Updated!")
            st.rerun()

    # --- ACTIONS BAR ---
    st.markdown("### 🛠️ Actions")
    c_act1, c_act2, c_act3, c_act4 = st.columns([1, 1, 1, 1.5])
    
    with c_act1:
        if st.button("🚫 Clear All Scouted", use_container_width=True):
            db.clear_scouted_jobs()
            st.session_state['selected_jobs'] = set()
            st.rerun()

    with c_act2:
        if st.button("📂 Archive Applied", use_container_width=True):
            db.archive_applied_jobs()
            st.rerun()

    with c_act3:
        # Check for Easy Apply batch
        easy_count = len([j for j in scouted_jobs if j.get('is_easy_apply') == True and f"{j['title']}-{j['company']}" in st.session_state['selected_jobs']])
        btn_label = f"🚀 Apply Selected ({easy_count})" if easy_count > 0 else "🚀 Apply Selected"
        if st.button(btn_label, type="primary", use_container_width=True, disabled=(easy_count == 0)):
            # Filter specifically selected Easy Apply jobs
            selected_easy_df = filtered[(filtered['is_easy_apply'] == True) & 
                                        (filtered.apply(lambda r: f"{r['title']}-{r['company']}" in st.session_state['selected_jobs'], axis=1))]
            render_batch_apply_confirm(selected_easy_df, db)

    with c_act4:
        selected_count = len(st.session_state['selected_jobs'])
        btn_label = f"🧠 Batch AI Analysis ({selected_count})" if selected_count > 0 else "🧠 Batch AI Analysis"
        if st.button(btn_label, type="secondary", use_container_width=True, disabled=(selected_count == 0)):
            st.session_state['show_batch_analysis_dialog'] = True
            st.rerun()

    if st.session_state.get('show_batch_analysis_dialog', False):
        # Filter specifically selected jobs
        selected_df = filtered[filtered.apply(lambda r: f"{r['title']}-{r['company']}" in st.session_state['selected_jobs'], axis=1)]
        render_batch_analysis_confirm(selected_df, db)

    # --- DATA GRID ---
    st.markdown("---")
    st.subheader(f"Results ({len(filtered)})")

    # Selection Helpers
    c_sel1, c_sel2, c_sel3 = st.columns([1, 1, 4])
    if c_sel1.button("✅ Select All Filtered", use_container_width=True):
        for idx, row in filtered.iterrows():
            st.session_state['selected_jobs'].add(f"{row['title']}-{row['company']}")
        st.rerun()
    if c_sel2.button("🚫 Clear Selection", use_container_width=True):
        st.session_state['selected_jobs'] = set()
        st.rerun()

    # Sort by Platform, then Title
    filtered = filtered.sort_values(by=["platform", "title"])

    # Cache for analysis status
    cache = db.load_cache()

    # Split into Analyzed and Pending
    analyzed_list = []
    pending_list = []
    
    for _, row in filtered.iterrows():
        resume_name = row.get('_role_name') or (list(st.session_state.get('resumes', {}).keys())[0] if st.session_state.get('resumes') else None)
        full_job_id = db.generate_job_id(row['title'], row['company'], resume_name)
        if full_job_id in cache and "error" not in cache[full_job_id]:
            analyzed_list.append(row)
        else:
            pending_list.append(row)

    def render_job_block(jobs, title_label):
        if not jobs: return
        st.markdown(f"### {title_label}")
        
        # Header Row
        h_cols = st.columns([0.4, 3.2, 1.8, 1.2, 4.4])
        h_cols[0].write("**Sel**")
        h_cols[1].write("**Job Title**")
        h_cols[2].write("**Company**")
        h_cols[3].write("**Type**")
        h_cols[4].write("**Actions**")

        for idx, row in enumerate(jobs):
            job_id = f"{row['title']}-{row['company']}"
            is_applied = (row.get("link") in st.session_state['applied_jobs'])
            is_selected = job_id in st.session_state['selected_jobs']
            
            resume_name = row.get('_role_name') or (list(st.session_state.get('resumes', {}).keys())[0] if st.session_state.get('resumes') else None)
            full_job_id = db.generate_job_id(row['title'], row['company'], resume_name)
            is_analyzed = full_job_id in cache and "error" not in cache[full_job_id]

            row_cols = st.columns([0.4, 3.2, 1.8, 1.2, 4.4])
            
            # 1. Selection Checkbox
            if row_cols[0].checkbox("Select", value=is_selected, key=f"sel_{job_id}_{idx}_{title_label}", label_visibility="collapsed"):
                st.session_state['selected_jobs'].add(job_id)
            else:
                st.session_state['selected_jobs'].discard(job_id)

            # 2. Title & Link
            title_display = f"[{row['title']}]({row['link']})"
            if is_applied: title_display = f"✅ {title_display}"
            row_cols[1].markdown(title_display)
            
            # Display the resume name used for scouting as sub-text
            res_label = row.get('_role_name') or row.get('Found_job') or "Default Resume"
            row_cols[1].caption(f"📄 {res_label}")

            # 3. Company
            row_cols[2].write(row['company'])

            # 4. Type
            row_cols[3].write("Easy Apply" if row['is_easy_apply'] else "Standard")

            # 5. Actions
            act_cols = row_cols[4].columns(8)
            
            # 1. AI Analysis
            results = cache.get(full_job_id, {})
            has_cl = "cover_letter" in results and results["cover_letter"]
            
            ai_icon = "🟢" if is_analyzed else "🔴"
            if act_cols[0].button(ai_icon, key=f"ai_{job_id}_{idx}_{title_label}", help="Run/View AI Analysis"):
                render_analysis_dialog(row.to_dict(), db)

            # 2. External Link
            if act_cols[1].button("🔗", key=f"lnk_{job_id}_{idx}_{title_label}", help="Open Job Link"):
                st.markdown(f'<meta http-equiv="refresh" content="0; url={row["link"]}">', unsafe_allow_html=True)

            # 3. Save Cover Letter
            if has_cl:
                if act_cols[2].button("✉️", key=f"save_{job_id}_{idx}_{title_label}", help="Save Cover Letter (PDF)"):
                    from tools.pdf_generator import generate_cover_letter_pdf
                    bot_config = db.load_bot_config()
                    custom_path = bot_config.get("settings", {}).get("cover_letter_path", "data/Cover_Letter.pdf")
                    path = generate_cover_letter_pdf(results["cover_letter"], output_path=custom_path)
                    if path:
                        st.toast(f"✅ Saved: {path}", icon="📄")
            else:
                act_cols[2].button("✉️", key=f"save_disabled_{job_id}_{idx}_{title_label}", help="Analyze first", disabled=True)

            # 4. Details
            if act_cols[3].button("ⓘ", key=f"det_{job_id}_{idx}_{title_label}", help="View Details"):
                st.info(f"Language: {row.get('language', 'Unknown')}\n\nDescription Snippet:\n{row.get('rich_description', 'No detailed description available.')[:1000]}...")

            # 5. Applied Status
            if act_cols[4].button("✔", key=f"status_{job_id}_{idx}_{title_label}", help="Mark Applied"):
                db.save_applied(full_job_id, job_data=row.to_dict(), analysis_data=results)
                db.delete_scouted_job(row['title'], row['company'])
                st.toast("🚀 Marked as Applied!", icon="✅")
                st.rerun()

            # 6. Park
            if act_cols[5].button("🅿️", key=f"park_{job_id}_{idx}_{title_label}", help="Park (Hide)"):
                db.park_job(row['title'], row['company'], row.to_dict())
                st.rerun()

            # 7. Delete
            if act_cols[6].button("🗑", key=f"del_{job_id}_{idx}_{title_label}", help="Delete"):
                db.delete_scouted_job(row['title'], row['company'])
                st.rerun()
                
            # 8. Block
            if act_cols[7].button("⛔", key=f"block_{job_id}_{idx}_{title_label}", help="Blacklist this Title"):
                bl = db.load_blacklist()
                if row['title'] not in bl['titles']:
                    bl['titles'].append(row['title'])
                    db.save_blacklist(bl['companies'], bl['titles'], bl['safe_phrases'])
                    db.delete_scouted_job(row['title'], row['company'])
                    st.toast(f"🚫 Blacklisted: {row['title']}")
                    st.rerun()

    # Render Blocks
    render_job_block(analyzed_list, "🟢 Analyzed Jobs")
    st.divider()
    render_job_block(pending_list, "🔴 Pending Analysis")

    # --- METRICS ---
    st.markdown("---")
    with st.expander("📈 Metrics and Visualisations", expanded=False):
        render_metrics_dashboard(filtered, st.session_state['applied_jobs'], len(db.load_parked()))

@st.dialog("🧠 Job Analysis", width="large")
def render_analysis_dialog(job, db):
    st.subheader(f"{job['title']} @ {job['company']}")

    # Resume Selection for analysis (Must be before job_id calc for resume-awareness)
    resume_options = list(st.session_state.get('resumes', {}).keys())
    
    # Auto-select the resume that was used for scouting
    default_index = 0
    scouted_role = job.get('_role_name') or job.get('Found_job')
    
    if scouted_role:
        for idx, r_name in enumerate(resume_options):
            # Match exact role name or check if the found_job string is inside the filename
            if scouted_role == r_name or (isinstance(scouted_role, str) and scouted_role.lower() in r_name.lower()):
                default_index = idx
                break
        
    selected_resume_key = st.selectbox("Analyze with Resume:", resume_options, index=default_index, key="analyze_resume_sel")
    selected_resume_data = st.session_state['resumes'].get(selected_resume_key, {})

    # Analysis logic (Resume-aware)
    job_id = db.generate_job_id(job['title'], job['company'], selected_resume_key)

    # Check if in cache
    cache = db.load_cache()
    is_analyzed = job_id in cache and "error" not in cache[job_id]
    analysis_results = cache.get(job_id, {})

    if st.button("🚀 Run/Refresh AI Analysis", type="primary"):
        from job_hunter.analysis_crew import JobAnalysisCrew
        with st.spinner("Brainstorming with LLM..."):
            crew = JobAnalysisCrew(job.get('rich_description', ''), selected_resume_data.get('text', ''))
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
    job_id = db.generate_job_id(job['title'], job['company'], resume_name)

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
                from tools.browser_llm import BrowserLLM
                bot_config = db.load_bot_config()
                headless = bot_config.get("settings", {}).get("ai_headless", True)
                browser_llm = BrowserLLM(provider="ChatGPT", headless=headless)
                jd = job.get('rich_description', '')
                context = f"Job: {job['title']} at {job['company']}\nJD: {jd}\nResume: {resume_data.get('text', '')}"
                prompt = f"Context:\n{context}\n\nQuestion: {user_query}\nAnswer in 2-3 sentences max."
                response = browser_llm.ask(prompt)
                st.write(response)
                browser_llm.close_tab()
                st.session_state.chat_history[job_id].append({"role": "assistant", "content": response})
                if job_id not in st.session_state['job_cache']: st.session_state['job_cache'][job_id] = {}
                st.session_state['job_cache'][job_id]['qna_history'] = st.session_state.chat_history[job_id]
                db.save_cache(job_id, st.session_state['job_cache'][job_id])
                st.rerun()

@st.dialog("🚀 Confirm Batch Apply")
def render_batch_apply_confirm(eligible_jobs, db):
    st.write(f"Ready to apply to **{len(eligible_jobs)}** jobs using Vision-Automation.")
    
    # Show mapping of job to resume (using our new _role_name field)
    resume_options = list(st.session_state.get('resumes', {}).keys())
    
    st.markdown("### Review Mappings")
    resume_mapping = {}
    for idx, row in eligible_jobs.iterrows():
        job_id = f"{row['title']}-{row['company']}"
        col1, col2 = st.columns([2, 1])
        col1.write(f"**{row['title']}** ({row['company']})")
        
        # Default index based on our saved _role_name
        default_idx = 0
        saved_role = row.get('_role_name')
        if saved_role in resume_options:
            default_idx = resume_options.index(saved_role)
            
        sel_resume = col2.selectbox("Resume:", resume_options, index=default_idx, key=f"batch_sel_{job_id}")
        resume_mapping[job_id] = sel_resume

    bot_config = db.load_bot_config()
    easy_phone = bot_config.get("profile", {}).get("phone", "+49 123 456789")

    if st.button("🚀 Start Vision Application", type="primary"):
        from job_hunter.applier import JobApplier
        applier = JobApplier(profile_name="default")
        status_box = st.empty()
        
        with st.spinner("Automating applications..."):
            applier.batch_apply_vision(
                jobs_df=eligible_jobs,
                phone_number=easy_phone,
                status_box=status_box,
                resume_mapping=resume_mapping
            )

        st.success("🎉 Vision Batch Apply Complete!")
        st.rerun()

    if st.button("❌ Cancel"):
        st.rerun()

@st.dialog("🧠 Confirm Batch Analysis")
def render_batch_analysis_confirm(jobs_to_analyze_df, db):
    resume_options = list(st.session_state.get('resumes', {}).keys())
    if not resume_options:
        st.warning("Please upload a resume first.")
        return
        
    # Smart Resume Awareness
    has_mixed_resumes = False
    all_have_resumes = True
    resume_names_found = set()
    
    for idx, row in jobs_to_analyze_df.iterrows():
        role = row.get('_role_name')
        if role:
            resume_names_found.add(role)
        else:
            all_have_resumes = False
            
    if len(resume_names_found) > 1:
        has_mixed_resumes = True

    selected_resume_key = None
    if all_have_resumes and not has_mixed_resumes:
        # All jobs use the same resume
        selected_resume_key = list(resume_names_found)[0]
        st.success(f"📌 Automatically using linked resume: **{selected_resume_key}**")
    elif all_have_resumes and has_mixed_resumes:
        # Mixed resumes, but all are tagged
        st.info("📌 Multiple roles detected. Each job will be analyzed with its **original scouting resume**.")
        # We still need a fallback for the UI logic below
        selected_resume_key = list(resume_names_found)[0] 
    else:
        # Some are missing, show the selectbox as fallback/override
        default_index = 0
        first_job = jobs_to_analyze_df.iloc[0]
        scouted_role = first_job.get('_role_name') or first_job.get('Found_job')
        if scouted_role:
            for idx, r_name in enumerate(resume_options):
                if scouted_role == r_name or (isinstance(scouted_role, str) and scouted_role.lower() in r_name.lower()):
                    default_index = idx
                    break
        selected_resume_key = st.selectbox("Analyze selected jobs with Resume:", resume_options, index=default_index)
    
    # Calculate how many are missing analysis
    cache = db.load_cache()
    missing_jobs = []
    
    for idx, row in jobs_to_analyze_df.iterrows():
        # Check analysis status (Resume-aware check)
        job_id = db.generate_job_id(row['title'], row['company'], selected_resume_key)
        # Include if not in cache OR if the cached result is an error
        if job_id not in cache or "error" in cache.get(job_id, {}):
            missing_jobs.append(row.to_dict())
            
    st.info(f"Out of the **{len(jobs_to_analyze_df)}** selected jobs, **{len(missing_jobs)}** are missing AI Analysis.")
    
    if len(missing_jobs) == 0:
        st.success("All jobs are already processed!")
        if st.button("Close"):
            st.session_state['show_batch_analysis_dialog'] = False
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
                status_text.text(f"Analyzing: {job['title']} at {job['company']} ({i+1}/{len(missing_jobs)})...")
                jd = job.get('rich_description') or ""
                context = f"Title: {job['title']}\nCompany: {job['company']}\nJD: {jd}"

                # Use the job's tagged resume if available, else use the batch-selected one
                job_resume_key = job.get('_role_name', selected_resume_key)
                job_resume_data = st.session_state['resumes'].get(job_resume_key, resume_data)
                
                crew = JobAnalysisCrew(context, job_resume_data.get('text', ''))
                # Pass close_after=False to keep session open during batch
                results = crew.run_analysis(use_browser=True, close_after=False)
                
                if results and "error" not in results:
                    job_id = db.generate_job_id(job['title'], job['company'], job_resume_key)
                    db.save_cache(job_id, results)
                    st.session_state['job_cache'][job_id] = results
                else:
                    st.toast(f"Skipped {job['company']} (Error). Keep monitoring.", icon="⚠️")
                
                progress_bar.progress((i + 1) / len(missing_jobs))
                time.sleep(1)  # Brief pause between jobs
            
            # Close browser when batch is fully done (only if we processed something)
            if missing_jobs:
                from tools.browser_llm import BrowserLLM
                bl = BrowserLLM(profile_name="llm_profile")
                bl.close_tab()
                
        st.success("Batch Analysis Complete!")
        st.session_state['show_batch_analysis_dialog'] = False
        st.rerun()

    if c2.button("❌ Cancel"):
        st.session_state['show_batch_analysis_dialog'] = False
        st.rerun()
