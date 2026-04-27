import streamlit as st
import pandas as pd
import base64
from job_hunter.data_manager import DataManager
from tools.logger import logger
from tools.browser_manager import BrowserManager
from ui.metrics import render_metrics_dashboard
import os

def get_mapped_resume_name(db, row):
    """Resolves the best resume filename for a given job row, prioritizing existing analysis."""
    resumes = st.session_state.get('resumes', {})
    cache = db.load_cache()
    title = row.get('title', 'Unknown')
    company = row.get('company', 'Unknown')

    # 1. PRIORITY: Check if an analysis already exists in cache for ANY resume
    # This ensures that if the user manually re-ran analysis with a different resume, 
    # the UI subtext updates to show THAT resume.
    for r_name in resumes:
        job_id = db.generate_job_id(title, company, r_name)
        if job_id in cache and "error" not in cache[job_id]:
            return r_name

    # 2. Match on _resume_filename (Original scouting mapping)
    res_file = row.get('_resume_filename')
    if res_file in resumes:
        return res_file
        
    # 3. Lookup role in history
    history = db.load_all_resume_history()
    role = row.get('_role_name') or row.get('Found_job')
    if role:
        for r_name, titles in history.items():
            if r_name in resumes and role in titles:
                return r_name
    
    # 4. Fuzzy match role in resume filenames
    if role:
        for r_name in resumes:
            if role.lower() in r_name.lower():
                return r_name
    
    # 5. Fallback to first resume
    return list(resumes.keys())[0] if resumes else "Default Resume"

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
    if 'applied_jobs_ids' not in st.session_state:
        # Build a set of title-company base IDs for robust matching
        applied_data = db.load_applied()
        ids = set()
        for k, v in applied_data.items():
            details = v.get('job_details', {})
            a_title = details.get('title') or details.get('Job Title', '')
            a_company = details.get('company') or details.get('Company', '')
            if a_title and a_company:
                a_title_clean = a_title.split('\n')[0].strip()
                ids.add(f"{a_title_clean}-{a_company.strip()}")
        st.session_state['applied_jobs_ids'] = ids

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
        
        # Check if we can bypass the dialog (if all selected jobs have clear mappings)
        can_bypass = False
        selected_df = filtered[filtered.apply(lambda r: f"{r['title']}-{r['company']}" in st.session_state['selected_jobs'], axis=1)]
        if not selected_df.empty:
            resume_options = list(st.session_state.get('resumes', {}).keys())
            has_all_links = True
            for _, row in selected_df.iterrows():
                res_name = get_mapped_resume_name(db, row)
                if not res_name or res_name not in resume_options:
                    has_all_links = False
                    break
            can_bypass = has_all_links

        if st.button(btn_label, type="secondary", use_container_width=True, disabled=(selected_count == 0)):
            if can_bypass:
                # Store the signal to run batch immediately
                st.session_state['run_batch_now'] = True
            else:
                st.session_state['show_batch_analysis_dialog'] = True
            st.rerun()

    # Handle immediate batch run (bypassing dialog)
    if st.session_state.get('run_batch_now', False):
        st.session_state['run_batch_now'] = False
        render_batch_analysis_confirm(selected_df, db, auto_start=True)

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
        resume_name = get_mapped_resume_name(db, row)
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
            # Match by title-company, not link (Indeed changes URLs between sessions)
            title_clean = row['title'].split('\n')[0].strip()
            base_id = f"{title_clean}-{row['company'].strip()}"
            is_applied = base_id in st.session_state.get('applied_jobs_ids', set())
            is_selected = job_id in st.session_state['selected_jobs']
            
            resume_name = get_mapped_resume_name(db, row)
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
            
            # Display the actual resume name resolved from history/metadata
            display_name = get_mapped_resume_name(db, row)
            row_cols[1].caption(f"📄 {display_name}")

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
    
    # Auto-select the resume that was resolved by our mapping logic (the "original" scouted resume)
    resolved_resume = get_mapped_resume_name(db, job)
    default_index = 0
    if resolved_resume in resume_options:
        default_index = resume_options.index(resolved_resume)
    
    # Key MUST be unique per job, otherwise Streamlit remembers stale selections from previous dialogs
    job_unique_key = f"analyze_resume_sel_{job['title']}_{job['company']}"
    selected_resume_key = st.selectbox("Analyze with Resume:", resume_options, index=default_index, key=job_unique_key)
    selected_resume_data = st.session_state['resumes'].get(selected_resume_key, {})

    # Detect if user switched to a different resume than the original
    is_resume_switched = (selected_resume_key != resolved_resume)

    # Analysis logic (Resume-aware)
    job_id = db.generate_job_id(job['title'], job['company'], selected_resume_key)
    original_job_id = db.generate_job_id(job['title'], job['company'], resolved_resume)

    # Check if in cache
    cache = db.load_cache()
    is_analyzed = job_id in cache and "error" not in cache[job_id]
    original_is_analyzed = original_job_id in cache and "error" not in cache[original_job_id]
    analysis_results = cache.get(job_id, {})

    # Show resume switch indicator
    if is_resume_switched:
        if is_analyzed:
            st.success(f"✅ Analysis exists for **{selected_resume_key}**. You can re-run to refresh.")
        elif original_is_analyzed:
            st.warning(f"⚠️ No analysis found for **{selected_resume_key}**. Showing results from **{resolved_resume}**. Click below to re-analyze with the new resume.")
            # Fallback: show original results until user re-runs
            analysis_results = cache.get(original_job_id, {})
        else:
            st.info(f"📋 Selected: **{selected_resume_key}**. Click below to run analysis.")

    # Dynamic button label
    if is_resume_switched and not is_analyzed:
        btn_label = f"🚀 Run AI Analysis with {selected_resume_key}"
    else:
        btn_label = "🚀 Run/Refresh AI Analysis"

    if st.button(btn_label, type="primary"):
        from job_hunter.analysis_crew import JobAnalysisCrew
        with st.spinner(f"Analyzing with **{selected_resume_key}**..."):
            crew = JobAnalysisCrew(job.get('rich_description', ''), selected_resume_data.get('text', ''))
            results = crew.run_analysis(use_browser=True)
            if results and "error" not in results:
                db.save_cache(job_id, results)
                st.session_state['job_cache'][job_id] = results
                st.success(f"✅ Analysis Complete with **{selected_resume_key}**!")
                st.rerun()
            else:
                st.error(f"Analysis failed: {results.get('error', 'Unknown error')}")

    # For display purposes: use the best available results
    display_results = analysis_results
    display_analyzed = bool(display_results and "error" not in display_results)


    # Tabs for results
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "💡 Intel", 
        "📋 Job Description",
        "📝 Cover Letter", 
        "🎯 ATS Match", 
        "📄 Strategized Resume", 
        "💬 Ask AI"
    ])

    with tab1:
        if not display_analyzed: st.info("Run AI Analysis first.")
        else:
            intel = display_results.get("company_intel", {})
            st.write(f"**Mission**: {intel.get('mission', 'N/A')}")
            st.write(f"**HQ**: {intel.get('headquarters', 'N/A')}")
            st.write(f"**Employees**: {intel.get('employees', 'N/A')}")
            st.write("**Key Facts**:")
            for f in intel.get('key_facts', []): st.markdown(f"• {f}")

    with tab2:
        st.markdown("### Job Description")
        jd_text = job.get('rich_description', 'No detailed description available.')
        st.markdown(jd_text, unsafe_allow_html=True)

    with tab3:
        if not display_analyzed: st.info("Run AI Analysis first.")
        else:
            if is_resume_switched and not is_analyzed:
                st.caption(f"⚠️ Showing cover letter from **{resolved_resume}**. Re-run to generate for **{selected_resume_key}**.")
            st.write(f"**Humanization Level:** {display_results.get('humanization_score', 0)}%")
            st.text_area("Cover Letter", display_results.get("cover_letter", ""), height=400)

    with tab4:
        if not display_analyzed: st.info("Run AI Analysis first.")
        else:
            if is_resume_switched and not is_analyzed:
                st.caption(f"⚠️ Showing ATS match from **{resolved_resume}**. Re-run for accurate match with **{selected_resume_key}**.")
            ats = display_results.get("ats_report", {})
            st.metric("Match Score", f"{ats.get('score', 0)}%")
            st.write("**Missing Skills:**")
            for s in ats.get("missing_skills", []): st.caption(f"❌ {s}")

    with tab5:
        if not display_analyzed: st.info("Run AI Analysis first.")
        else:
            if is_resume_switched and not is_analyzed:
                st.caption(f"⚠️ Showing tailored resume from **{resolved_resume}**. Re-run to tailor for **{selected_resume_key}**.")
            c_res1, c_res2 = st.columns([1, 1])
            with c_res1:
                st.text_area("Tailored Resume", display_results.get("tailored_resume", ""), height=600)
            with c_res2:
                st.markdown("### Original Resume Preview")
                if "pdf_bytes" in selected_resume_data:
                    base64_pdf = base64.b64encode(selected_resume_data['pdf_bytes']).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                else:
                    st.warning("PDF bytes not found in session. Try re-uploading.")

    with tab6:
        render_chat_tab(job, selected_resume_key, selected_resume_data, display_results, db)


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

@st.dialog("🧠 Confirm Batch Analysis", width="large")
def render_batch_analysis_confirm(jobs_to_analyze_df, db, auto_start=False):
    resume_options = list(st.session_state.get('resumes', {}).keys())
    if not resume_options:
        st.warning("Please upload a resume first.")
        return
    
    # Mapping table
    resume_mapping = {}
    missing_jobs = []
    cache = db.load_cache()
    
    for idx, row in jobs_to_analyze_df.iterrows():
        job_id_full = f"{row['title']}-{row['company']}"
        
        # Resolve using helper
        sel_resume = get_mapped_resume_name(db, row)
        default_idx = resume_options.index(sel_resume) if sel_resume in resume_options else 0
        
        if not auto_start:
            col1, col2 = st.columns([2, 1])
            col1.write(f"**{row['title']}** ({row['company']})")
            sel_resume = col2.selectbox("Resume:", resume_options, index=default_idx, key=f"batch_ana_sel_{job_id_full}")
        
        resume_mapping[job_id_full] = sel_resume

        # Check if actually missing
        job_cache_id = db.generate_job_id(row['title'], row['company'], sel_resume)
        if job_cache_id not in cache or "error" in cache.get(job_cache_id, {}):
            missing_jobs.append(row.to_dict())

    if not auto_start:
        st.divider()
        st.info(f"Out of the **{len(jobs_to_analyze_df)}** selected jobs, **{len(missing_jobs)}** require AI Analysis.")
        
        if not missing_jobs:
            st.success("All selected jobs are already analyzed!")
            if st.button("Close"):
                st.session_state['show_batch_analysis_dialog'] = False
                st.rerun()
            return

    # If auto_start and nothing missing, we can just finish
    if auto_start and not missing_jobs:
        st.session_state['show_batch_analysis_dialog'] = False
        return

    c1, c2 = st.columns(2)
    start_triggered = auto_start
    
    if not auto_start:
        if c1.button("✅ Run Background Batch", type="primary"):
            start_triggered = True
        if c2.button("❌ Cancel"):
            st.session_state['show_batch_analysis_dialog'] = False
            st.rerun()

    if start_triggered:
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.empty()
        
        from job_hunter.analysis_crew import JobAnalysisCrew
        from tools.browser_llm import BrowserLLM
        import time
        
        # Initialize browser once for the whole batch
        bot_config = db.load_bot_config()
        headless = bot_config.get("settings", {}).get("ai_headless", True)
        provider = os.getenv("BROWSER_LLM_PROVIDER", "ChatGPT")
        browser_llm = BrowserLLM(provider=provider, profile_name="llm_profile", headless=headless)
        
        logs = []
        def add_log(msg):
            logs.append(f"- {msg}")
            log_area.markdown("\n".join(logs[-5:])) # Show last 5 logs

        try:
            for i, job in enumerate(missing_jobs):
                job_full_id = f"{job['title']}-{job['company']}"
                selected_resume = resume_mapping[job_full_id]
                resume_data = st.session_state['resumes'].get(selected_resume, {})
                
                status_text.text(f"Processing {i+1}/{len(missing_jobs)}: {job['title']}")
                add_log(f"Starting {job['company']}...")
                
                jd = job.get('rich_description') or ""
                context = f"Title: {job['title']}\nCompany: {job['company']}\nJD: {jd}"
                
                crew = JobAnalysisCrew(context, resume_data.get('text', ''))
                # Pass existing browser_llm and clear_chat=True
                results = crew.run_analysis(use_browser=True, close_after=False, browser_llm=browser_llm, clear_chat=True)
                
                if results and "error" not in results:
                    job_cache_id = db.generate_job_id(job['title'], job['company'], selected_resume)
                    db.save_cache(job_cache_id, results)
                    st.session_state['job_cache'][job_cache_id] = results
                    add_log(f"✅ Success: {job['company']}")
                else:
                    err = results.get('error', 'Unknown Error')
                    add_log(f"❌ Failed: {job['company']} ({err[:30]}...)")
                    st.toast(f"Skipped {job['company']}", icon="⚠️")
                
                progress_bar.progress((i + 1) / len(missing_jobs))
                time.sleep(1)
        finally:
            # Always close tab at the end of batch
            browser_llm.close_tab()
                
        st.success("Batch Analysis Complete!")
        st.session_state['show_batch_analysis_dialog'] = False
        st.session_state['run_batch_now'] = False
        st.rerun()
