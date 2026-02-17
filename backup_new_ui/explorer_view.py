import streamlit as st
import pandas as pd
import time
from job_hunter.data_manager import DataManager
from job_hunter.applier import JobApplier
from job_hunter.analysis_crew import JobAnalysisCrew
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

    # --- Blacklist ---
    with st.expander("🚫 Blacklist Quick Manager"):
        bl_data = db.load_blacklist()
        c1, c2, c3 = st.columns(3)
        new_c = c1.text_area("Block Companies", "; ".join(bl_data.get("companies", [])))
        new_t = c2.text_area("Block Titles", "; ".join(bl_data.get("titles", [])))
        new_s = c3.text_area("Safe Phrases", "; ".join(bl_data.get("safe_phrases", [])))
        if st.button("Save Blacklist"):
            db.save_blacklist([x.strip() for x in new_c.split(';') if x.strip()],
                             [x.strip() for x in new_t.split(';') if x.strip()],
                             [x.strip() for x in new_s.split(';') if x.strip()])
            st.toast("Blacklist updated!")

    applied_jobs = db.load_applied()
    df["Status"] = df.apply(lambda r: get_job_status(r, applied_jobs), axis=1)

    # --- Bulk Actions ---
    col_a1, col_a2 = st.columns(2)
    if col_a1.button("🤖 Auto Easy Apply All"):
        run_bulk_apply(df, db)

    if col_a2.button("🧹 Archive Applied"):
        removed = db.archive_applied_jobs()
        st.success(f"Archived {removed} jobs.")
        st.rerun()

    # --- Data Table ---
    st.subheader("Current Batch")
    display_df = df[["Status", "Job Title", "Company", "Location", "Platform", "Easy Apply", "Language"]]
    st.dataframe(display_df, use_container_width=True)

    # --- Job Selector ---
    job_options = [f"{r['Job Title']} @ {r['Company']}" for i, r in df.iterrows()]
    selected_job_str = st.selectbox("Select a job to process", job_options)

    if selected_job_str:
        idx = job_options.index(selected_job_str)
        job_row = df.iloc[idx]
        render_job_details(job_row, db)

def run_bulk_apply(df, db):
    candidates = df[(df["Easy Apply"] == True) & (df["Status"] == "")]
    if candidates.empty:
        st.info("No Easy Apply candidates found.")
        return

    status = st.empty()
    applier = JobApplier()
    for i, (_, row) in enumerate(candidates.iterrows()):
        status.info(f"Applying [{i+1}/{len(candidates)}]: {row['Job Title']}...")
        success, msg, _ = applier.apply(row['Web Address'], row['Platform'])
        if success:
            db.save_applied(f"{row['Job Title']}-{row['Company']}", row.to_dict())
            st.toast(f"✅ Applied: {row['Job Title']}")
        else:
            st.error(f"❌ Failed: {row['Job Title']} - {msg}")
    st.success("Bulk apply finished.")
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
        if st.button("✨ Run AI Analysis", use_container_width=True):
            run_single_analysis(row, db)

        if row['Easy Apply']:
            if st.button("🤖 Auto Apply Now", use_container_width=True, type="primary"):
                applier = JobApplier()
                success, msg, _ = applier.apply(row['Web Address'], row['Platform'])
                if success:
                    db.save_applied(jid, row.to_dict())
                    st.success("Applied successfully!")
                else:
                    st.error(f"Failed: {msg}")

    # Description
    desc = row.get('Rich Description') or row.get('Job Description') or ""
    with st.expander("📝 View Description", expanded=False):
        st.write(desc)

    # AI Results
    cache = db.load_cache()
    if jid in cache:
        res = cache[jid]
        t1, t2, t3, t4 = st.tabs(["📊 Intel", "📝 Cover Letter", "🎯 ATS Match", "💡 Resume Strategy"])
        t1.markdown(res.get('intel', 'N/A'))
        t2.code(res.get('cover_letter', 'N/A'), language='markdown')
        t3.markdown(res.get('ats', 'N/A'))
        t4.markdown(res.get('resume', 'N/A'))

def run_single_analysis(row, db):
    jid = f"{row['Job Title']}-{row['Company']}"
    desc = row.get('Rich Description') or row.get('Job Description') or ""
    if not desc:
        st.error("No job description available for analysis.")
        return

    with st.spinner("🧠 AI is thinking..."):
        context = f"Title: {row['Job Title']}\nCompany: {row['Company']}\nJD:\n{desc}"
        resume_text = "" # Should get from session state
        for role, rdata in st.session_state['resumes'].items():
            if rdata.get('text'):
                resume_text = rdata['text']
                break

        crew = JobAnalysisCrew(context, resume_text)
        results = crew.run_analysis(use_browser=st.session_state.get('use_browser_analysis', True))
        if results and "error" not in results:
            db.save_cache(jid, results)
            st.success("Analysis complete!")
            st.rerun()
        else:
            st.error(f"Analysis failed: {results.get('error') if results else 'Unknown error'}")
