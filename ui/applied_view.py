import streamlit as st
import pandas as pd
from ui.metrics import render_metrics_dashboard

@st.dialog("📋 Application Details", width="large")
def show_details_dialog(job_record):
    details = job_record.get('job_details', {})
    analysis = job_record.get('ai_analysis', {})
    
    st.title(f"{details.get('Job Title', 'Job')} @ {details.get('Company', 'Company')}")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🧠 Company Intel", "✉️ Cover Letter", "📄 Job Description", "👤 Resume Used"])
    
    with tab1:
        intel = analysis.get('company_intel', {})
        if intel:
            st.subheader("🏢 Business Intelligence")
            st.markdown(f"**Mission:** {intel.get('mission', 'N/A')}")
            st.markdown("**Key Facts:**")
            for fact in intel.get('key_facts', []):
                st.markdown(f"- {fact}")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**HQ:** {intel.get('headquarters', 'N/A')}")
                st.markdown(f"**Employees:** {intel.get('employees', 'N/A')}")
            with col_b:
                st.markdown(f"**Branches:** {intel.get('branches', 'N/A')}")
        else:
            st.info("No AI Intel available for this application.")

    with tab2:
        cl = analysis.get('cover_letter')
        if cl:
            st.text_area("Generated Cover Letter", cl, height=400)
            st.download_button("📥 Download Cover Letter", cl, file_name=f"Cover_Letter_{details.get('Company')}.txt")
        else:
            st.info("No Cover Letter was generated for this application.")

    with tab3:
        jd = details.get('Rich Description') or details.get('description')
        if jd:
            st.markdown("### Job Description")
            st.markdown(jd)
        else:
            st.info("No Job Description text saved.")

    with tab4:
        # Check for tailored resume first
        tailored = analysis.get('tailored_resume')
        if tailored:
            st.markdown("### ✨ Tailored Resume Highlights")
            st.markdown(tailored)
        
        # Also show which base resume was used if tracked
        resume_file = details.get('_resume_filename') or job_record.get('job_details', {}).get('_resume_filename')
        if resume_file:
            st.markdown(f"**Base Resume Used:** `{resume_file}`")
        
        if not tailored and not resume_file:
            st.info("No specific resume tracking data found for this record.")

def render_applied_view(db):
    st.title("📂 Applied Jobs History")

    # --- RENDER DASHBOARD ---
    current_scouted_data = db.load_scouted()
    if current_scouted_data:
        current_df_stats = pd.DataFrame(current_scouted_data)
    else:
        current_df_stats = pd.DataFrame(columns=["Platform"])

    # Ensure applied_jobs is in session state
    if 'applied_jobs' not in st.session_state or not st.session_state['applied_jobs']:
         st.session_state['applied_jobs'] = db.load_applied()

    applied_dict = st.session_state['applied_jobs']
    render_metrics_dashboard(current_df_stats, applied_dict, len(db.load_parked()))

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
                      audit_result = auditor.run_audit(resume_text_audit)
                      st.session_state['last_audit_result'] = audit_result
                      db.save_audit_report(audit_result)
                      st.toast("Audit Complete!")

        if st.session_state.get('last_audit_result'):
             st.markdown("### ♟️ Grand Master Strategy Report")
             st.markdown(st.session_state['last_audit_result'])

    # --- APPLIED JOBS LIST ---
    if not applied_dict:
        st.info("No applied jobs yet.")
        return

    st.success(f"You have applied to {len(applied_dict)} jobs.")
    st.info("💡 **Tip:** Click the checkbox on the left of any row to view its full AI details.")

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
        
        # SELECTION EVENT
        event = st.dataframe(
            df,
            column_config={
                "Job ID": None,
                "Link": st.column_config.LinkColumn("Link", display_text="Open")
            },
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="applied_jobs_grid"
        )
        
        # Trigger Dialog on Selection (Robust checking)
        try:
            # Check if event is the new Streamlit SelectionEvent object or a dict
            rows = []
            if hasattr(event, "selection"):
                rows = event.selection.rows
            elif isinstance(event, dict):
                rows = event.get("selection", {}).get("rows", [])
            
            if rows:
                selected_row_idx = rows[0]
                selected_job_id = df.iloc[selected_row_idx]["Job ID"]
                job_record = applied_dict.get(selected_job_id)
                if job_record:
                    show_details_dialog(job_record)
        except Exception as e:
            st.error(f"Selection error: {e}")

        st.markdown("---")
        st.caption("Manage Records")
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            selected_jid = st.selectbox(
                "Select Record:", 
                options=[row["Job ID"] for row in grid_data], 
                format_func=lambda x: f"{next((item['Applied Position'] for item in grid_data if item['Job ID'] == x), '')} @ {next((item['Company Name'] for item in grid_data if item['Job ID'] == x), '')}",
                key="details_selector"
            )
        
        with col2:
            st.write("")
            st.write("")
            if st.button("🔍 View Details", use_container_width=True):
                rec = applied_dict.get(selected_jid)
                if rec:
                    show_details_dialog(rec)
        
        with col3:
            st.write("")
            st.write("")
            if st.button("🗑️ Delete", use_container_width=True):
                db.delete_applied(selected_jid)
                st.session_state['applied_jobs'] = db.load_applied()
                st.rerun()
