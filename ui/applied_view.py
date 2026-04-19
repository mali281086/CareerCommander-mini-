import streamlit as st
import pandas as pd
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

    grid_data = []
    for jid, data in items:
        details = data.get('job_details', {})
        grid_data.append({
            "Job ID": jid,
            "Applied Position": details.get('Job Title', 'N/A'),
            "Company Name": details.get('Company', 'N/A'),
            "Applied on": data.get('created_at', 'N/A'),
            "Applied against Job Title": details.get('Found_job', 'N/A'),
            "Platform": details.get('Platform', 'N/A'),
            "Link": details.get('Web Address') or details.get('link') or ""
        })

    if grid_data:
        df = pd.DataFrame(grid_data)
        st.dataframe(
            df,
            column_config={
                "Job ID": None,
                "Link": st.column_config.LinkColumn("Link", display_text="Open")
            },
            hide_index=True,
            use_container_width=True
        )

        st.markdown("---")
        st.caption("Manage Records")
        col1, col2 = st.columns([3, 1])
        with col1:
            del_job_id = st.selectbox(
                "Select Application to Delete:", 
                options=[row["Job ID"] for row in grid_data], 
                format_func=lambda x: f"{next((item['Applied Position'] for item in grid_data if item['Job ID'] == x), '')} @ {next((item['Company Name'] for item in grid_data if item['Job ID'] == x), '')}"
            )
        with col2:
            st.write("")
            st.write("")
            if st.button("🗑️ Delete", use_container_width=True):
                db.delete_applied(del_job_id)
                st.session_state['applied_jobs'] = db.load_applied()
                st.rerun()
