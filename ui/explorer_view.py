import streamlit as st
import pandas as pd
import time
import base64
from job_hunter.data_manager import DataManager
from job_hunter.applier import JobApplier
from job_hunter.analysis_crew import JobAnalysisCrew
from job_hunter.content_fetcher import ContentFetcher
from ui.utils import load_and_normalize_data, get_job_status
from ui.components import render_metrics_dashboard

def render_explorer_view():
    st.title("🔎 Mission Results")
    db = DataManager()
    df = load_and_normalize_data()

    applied_jobs = db.load_applied()
    parked = db.load_parked()
    render_metrics_dashboard(df, applied_jobs, len(parked))
    st.divider()

    if df.empty:
        st.warning("No data found. Please run a mission first.")
        if st.button("Back to Home"): st.session_state['page'] = 'home'; st.rerun()
        st.stop()

    # --- 1. SETTINGS & FILTERS ---
    with st.expander("🛠️ View Settings & Blacklist", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("##### 🚫 Blacklist")
            bl_data = db.load_blacklist()
            new_c = st.text_area("Block Companies", "; ".join(bl_data.get("companies", [])), key="bl_c")
            new_t = st.text_area("Block Titles", "; ".join(bl_data.get("titles", [])), key="bl_t")
            new_s = st.text_area("Safe Phrases", "; ".join(bl_data.get("safe_phrases", [])), key="bl_s")
            if st.button("Save Blacklist"):
                db.save_blacklist([x.strip() for x in new_c.split(';') if x.strip()],
                                 [x.strip() for x in new_t.split(';') if x.strip()],
                                 [x.strip() for x in new_s.split(';') if x.strip()])
                st.toast("Blacklist updated!")

        with c2:
            st.markdown("##### 🌍 Filter")
            if "Platform" in df.columns:
                platforms = ["All"] + df["Platform"].unique().tolist()
                sel_platform = st.selectbox("Platform", platforms)
                if sel_platform != "All":
                    df = df[df["Platform"] == sel_platform]

            if "Language" in df.columns:
                langs = ["All"] + df["Language"].unique().tolist()
                sel_lang = st.selectbox("Language", langs)
                if sel_lang != "All":
                    df = df[df["Language"] == sel_lang]

    # --- 2. BULK ACTIONS ---
    st.subheader("⚡ Quick Actions")
    col_a1, col_a2, col_a3, col_a4 = st.columns(4)

    if col_a1.button("🤖 Auto Easy Apply All", use_container_width=True, type="primary"):
        run_bulk_apply(df, db)

    if col_a2.button("🕵️ Deep Scrape All", use_container_width=True):
        run_bulk_deep_scrape(df, db)

    if col_a3.button("🧹 Archive Applied", use_container_width=True):
        removed = db.archive_applied_jobs()
        st.success(f"Archived {removed} jobs.")
        st.cache_data.clear()
        st.rerun()

    if col_a4.button("🗑️ Clear Current Batch", use_container_width=True):
        # Implementation for clearing scouted jobs
        with open("data/scouted_jobs.json", "w") as f: f.write("[]")
        st.cache_data.clear()
        st.rerun()

    # --- 3. DATA EDITOR ---
    # Add control columns
    df.insert(0, "Select", False)
    df["Applied"] = df.apply(lambda r: get_job_status(r, applied_jobs) != "", axis=1)
    df["Park"] = False
    df["Delete"] = False

    edited_df = st.data_editor(
        df,
        column_config={
            "Select": st.column_config.CheckboxColumn(required=True),
            "Applied": st.column_config.CheckboxColumn(),
            "Park": st.column_config.CheckboxColumn(),
            "Delete": st.column_config.CheckboxColumn(),
            "Web Address": st.column_config.LinkColumn()
        },
        disabled=["Job Title", "Company", "Location", "Platform", "Language", "Easy Apply"],
        hide_index=True,
        use_container_width=True,
        key="explorer_editor"
    )

    # Handle Editor Changes
    handle_editor_changes(edited_df, df, db)

    # --- 4. JOB DETAILS & ANALYSIS ---
    selected_jid = st.session_state.get("selected_job_id")
    if selected_jid:
        # Find the row in the original dataframe
        job_row = None
        for i, r in df.iterrows():
            if f"{r['Job Title']}-{r['Company']}" == selected_jid:
                job_row = r
                break

        if job_row is not None:
            render_job_details(job_row, db)

def handle_editor_changes(edited_df, original_df, db):
    for idx, row in edited_df.iterrows():
        jid = f"{row['Job Title']}-{row['Company']}"

        # 1. Selection
        if row['Select'] and st.session_state.get("selected_job_id") != jid:
            st.session_state["selected_job_id"] = jid
            st.rerun()
        elif not row['Select'] and st.session_state.get("selected_job_id") == jid:
            st.session_state["selected_job_id"] = None
            st.rerun()

        # 2. Delete
        if row['Delete']:
            db.delete_scouted_job(row['Job Title'], row['Company'])
            st.toast(f"Deleted {row['Job Title']}")
            st.cache_data.clear()
            st.rerun()

        # 3. Park
        if row['Park']:
            db.park_job(row['Job Title'], row['Company'], row.to_dict())
            st.toast(f"Parked {row['Job Title']}")
            st.cache_data.clear()
            st.rerun()

        # 4. Applied status toggle
        is_in_db = jid in st.session_state.get('applied_jobs', {})
        if row['Applied'] and not is_in_db:
            db.save_applied(jid, row.to_dict())
            st.toast(f"Marked as applied: {row['Job Title']}")
            st.rerun()
        elif not row['Applied'] and is_in_db:
            db.delete_applied(jid)
            st.toast(f"Removed from applied: {row['Job Title']}")
            st.rerun()

def run_bulk_apply(df, db):
    # Support all 5 platforms in the batch apply if marked as Easy Apply
    candidates = df[(df["Easy Apply"] == True) & (df["Status"] == "")]
    if candidates.empty:
        st.info("No Easy Apply candidates found.")
        return

    prog = st.progress(0)
    status = st.empty()
    applier = JobApplier()
    applied_count = 0

    for i, (_, row) in enumerate(candidates.iterrows()):
        status.info(f"Applying [{i+1}/{len(candidates)}]: {row['Job Title']}...")
        success, msg, _ = applier.apply(row['Web Address'], row['Platform'])
        if success:
            db.save_applied(f"{row['Job Title']}-{row['Company']}", row.to_dict())
            applied_count += 1
        prog.progress((i+1)/len(candidates))

    st.success(f"Bulk apply finished. Applied to {applied_count} jobs.")
    st.cache_data.clear()
    st.rerun()

def run_bulk_deep_scrape(df, db):
    status = st.empty()
    fetcher = ContentFetcher()
    scouted_list = db.load_scouted()

    updated_count = 0
    for i, job in enumerate(scouted_list):
        if not job.get('rich_description'):
            status.info(f"Scraping [{i+1}/{len(scouted_list)}]: {job.get('title')}...")
            details = fetcher.fetch_details(job.get('link'), job.get('platform'))
            if details:
                job['rich_description'] = details.get('description', '')
                job['is_easy_apply'] = details.get('is_easy_apply', job.get('is_easy_apply', False))
                job['language'] = details.get('language', 'Unknown')
                updated_count += 1

    db.save_scouted_jobs(scouted_list)
    st.success(f"Deep scrape complete. Updated {updated_count} jobs.")
    st.cache_data.clear()
    st.rerun()

def render_job_details(row, db):
    st.divider()
    jid = f"{row['Job Title']}-{row['Company']}"

    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader(row['Job Title'])
        st.write(f"🏢 **{row['Company']}** | 📍 {row['Location']} | 🌐 {row['Platform']}")
        st.write(f"🔗 [View Job]({row['Web Address']})")

    with c2:
        if st.button("✨ Run AI Analysis", use_container_width=True, type="primary"):
            run_single_analysis(row, db)

        if row['Easy Apply']:
            if st.button("🤖 Auto Apply Now", use_container_width=True):
                applier = JobApplier()
                success, msg, _ = applier.apply(row['Web Address'], row['Platform'])
                if success:
                    db.save_applied(jid, row.to_dict())
                    st.success("Applied successfully!")
                else:
                    st.error(f"Failed: {msg}")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Description", "📊 Intel", "📝 Cover Letter", "🎯 ATS Match", "📄 Resume"])

    with tab1:
        desc = row.get('Rich Description') or row.get('Job Description') or "No description available."
        st.write(desc)

    cache = db.load_cache()
    res = cache.get(jid, {})
    is_analyzed = bool(res)

    with tab2:
        if is_analyzed:
            intel = res.get('company_intel', {})
            st.markdown(f"**Mission:** {intel.get('mission', 'N/A')}")
            st.write("**Key Facts:**")
            for f in intel.get('key_facts', []): st.write(f"- {f}")
        else:
            st.info("Run AI Analysis to see company intel.")

    with tab3:
        if is_analyzed:
            h_score = res.get('humanization_score', 0)
            st.metric("Humanization Score", f"{h_score}%")
            st.progress(h_score/100)
            st.text_area("Cover Letter", res.get('cover_letter', 'N/A'), height=400)
        else:
            st.info("Run AI Analysis to generate a cover letter.")

    with tab4:
        if is_analyzed:
            ats = res.get('ats_report', {})
            score = ats.get('score', 0)
            st.metric("ATS Match Score", f"{score}%")
            st.progress(score/100)
            st.write("**Missing Skills:**")
            for s in ats.get('missing_skills', []): st.write(f"- {s}")
        else:
            st.info("Run AI Analysis to see ATS matching.")

    with tab5:
        # Resume Visualization
        available_resumes = st.session_state.get('resumes', {})
        if available_resumes:
            # Try to match resume by keyword used
            search_kw = row.get('Found_job', '')
            matched_resume = None
            if search_kw in available_resumes:
                matched_resume = available_resumes[search_kw]
            else:
                matched_resume = list(available_resumes.values())[0] # Fallback

            if matched_resume.get('bytes'):
                b64_pdf = base64.b64encode(matched_resume['bytes']).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
            else:
                st.text_area("Resume Text", matched_resume.get('text', ''), height=400)
        else:
            st.warning("No resumes uploaded.")

def run_single_analysis(row, db):
    jid = f"{row['Job Title']}-{row['Company']}"
    desc = row.get('Rich Description') or row.get('Job Description') or ""
    if not desc:
        st.error("No job description available for analysis.")
        return

    with st.spinner("🧠 AI is thinking..."):
        context = f"Title: {row['Job Title']}\nCompany: {row['Company']}\nJD:\n{desc}"

        # Get appropriate resume
        available_resumes = st.session_state.get('resumes', {})
        resume_text = ""
        if available_resumes:
            search_kw = row.get('Found_job', '')
            if search_kw in available_resumes:
                resume_text = available_resumes[search_kw].get('text', '')
            else:
                resume_text = list(available_resumes.values())[0].get('text', '')

        crew = JobAnalysisCrew(context, resume_text)
        results = crew.run_analysis(use_browser=st.session_state.get('use_browser_analysis', True))
        if results and "error" not in results:
            db.save_cache(jid, results)
            st.success("Analysis complete!")
            st.rerun()
        else:
            st.error(f"Analysis failed: {results.get('error') if results else 'Unknown error'}")
