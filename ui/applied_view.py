import streamlit as st
import pandas as pd
import json
from ui.metrics import render_metrics_dashboard

def render_applied_view(db):
    st.title("📂 Applied Jobs History")

    # --- RENDER DASHBOARD ---
    current_scouted_data = db.load_scouted()
    if current_scouted_data:
        current_df_stats = pd.DataFrame(current_scouted_data)
    else:
        current_df_stats = pd.DataFrame(columns=["Platform"])

    render_metrics_dashboard(current_df_stats, st.session_state['applied_jobs'], len(db.load_parked()))

    # --- GRAND MASTER STRATEGIST (CAREER AUDIT) ---
    st.markdown("---")
    with st.expander("♟️ Career Strategy Audit (Grand Master)", expanded=False):
        st.write("Analyze your applied jobs collectively to find out why you are not getting interviews.")

        # Resume Selection
        resume_options = list(st.session_state.get('resumes', {}).keys())
        selected_resume_audit = st.selectbox("Select Resume for Audit", resume_options, key="audit_resume_sel")
        resume_text_audit = st.session_state['resumes'].get(selected_resume_audit, {}).get('text', "")

        if st.button("🚀 Run Audit", type="primary"):
             if not resume_text_audit:
                 st.error("No resume found!")
             else:
                 with st.spinner("Analyzing Jobs..."):
                     from job_hunter.career_auditor import CareerAuditor
                     auditor = CareerAuditor()
                     # Auditor will need updating to use BrowserLLM
                     audit_result = auditor.run_audit(resume_text_audit)
                     st.session_state['last_audit_result'] = audit_result
                     db.save_audit_report(audit_result)
                     st.toast("Audit Complete!")

        if st.session_state.get('last_audit_result'):
             st.markdown("### ♟️ Grand Master Strategy Report")
             st.markdown(st.session_state['last_audit_result'])

    # --- APPLIED JOBS LIST ---
    applied_dict = st.session_state['applied_jobs']
    if not applied_dict:
        st.info("No applied jobs yet.")
        return

    st.success(f"You have applied to {len(applied_dict)} jobs.")

    # Filter/Sort
    sort_by = st.selectbox("Sort By", ["Newest First", "Oldest First", "Platform"])

    items = list(applied_dict.items())
    if sort_by == "Newest First":
        items.reverse()
    elif sort_by == "Platform":
        items.sort(key=lambda x: x[1].get('job_details', {}).get('Platform', ''))

    for jid, data in items:
        details = data.get('job_details', {})
        with st.expander(f"{details.get('Job Title')} @ {details.get('Company')} ({details.get('Platform')})"):
            st.write(f"**Applied on:** {data.get('created_at', 'N/A')}")
            st.write(f"**Target Role:** {details.get('Found_job', 'N/A')}")
            st.write(f"**Link:** [Open]({details.get('Web Address') or details.get('link')})")

            if st.button("🗑️ Delete Application Record", key=f"del_app_{jid}"):
                db.delete_applied_job(jid)
                st.session_state['applied_jobs'] = db.load_applied()
                st.rerun()
