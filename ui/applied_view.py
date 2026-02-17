import streamlit as st
import base64
from job_hunter.data_manager import DataManager
from job_hunter.model_factory import get_llm
from job_hunter.career_auditor import CareerAuditor
from ui.components import render_metrics_dashboard
from ui.utils import load_and_normalize_data

def render_applied_view():
    st.title("📂 Applied Jobs & Strategy")
    db = DataManager()
    applied = db.load_applied()
    scouted_df = load_and_normalize_data()
    parked = db.load_parked()

    # --- 1. METRICS DASHBOARD ---
    render_metrics_dashboard(scouted_df, applied, len(parked))
    st.divider()

    if not applied:
        st.info("No applied jobs yet. Start applying from the Explorer!")
        return

    # --- 2. CAREER STRATEGY AUDIT ---
    with st.expander("🛡️ Career Strategy Audit (Grand Master)", expanded=False):
        st.subheader("Generate Global Strategy Report")
        st.write("Analyzes all applied jobs to identify patterns and refine your career strategy.")

        # Need resume text for audit
        available_resumes = st.session_state.get('resumes', {})
        if not available_resumes:
            st.warning("Please upload a resume on the Home page to run the audit.")
        else:
            selected_resume_for_audit = st.selectbox("Select Resume for Audit", list(available_resumes.keys()))
            resume_text = available_resumes[selected_resume_for_audit].get('text', '')

            if st.button("🚀 Run Grand Master Audit", use_container_width=True):
                with st.spinner("Analyzing your application history..."):
                    auditor = CareerAuditor()
                    report = auditor.run_audit(resume_text)
                    if report:
                        db.save_audit_report(report)
                        st.success("Strategy Audit Complete!")

        audit_report = db.load_audit_report()
        if audit_report:
            st.markdown(audit_report, unsafe_allow_html=True)

    # --- 3. APPLIED JOBS LIST & DETAILS ---
    st.subheader("Applied History")
    job_ids = list(applied.keys())
    selected_id = st.selectbox("Select an application to review", job_ids)

    if selected_id:
        record = applied[selected_id]
        details = record.get('job_details', {})
        analysis = record.get('ai_analysis', {})

        st.subheader(f"{details.get('Job Title', details.get('title'))} @ {details.get('Company', details.get('company'))}")
        st.caption(f"Applied on: {record.get('created_at')}")

        t1, t2, t3 = st.tabs(["📊 Analysis Results", "📄 Resume & Persona", "💬 Prep Chat"])

        with t1:
            render_applied_analysis(analysis)

        with t2:
            render_applied_resume(details)

        with t3:
            render_prep_chat(selected_id, details, analysis, db)

def render_applied_analysis(analysis):
    if not analysis:
        st.info("No AI analysis found for this application.")
        return

    c1, c2 = st.columns(2)
    with c1:
        intel = analysis.get('company_intel', {})
        st.markdown(f"**Mission:** {intel.get('mission', 'N/A')}")
        st.write("**Key Facts:**")
        for f in intel.get('key_facts', []): st.write(f"- {f}")

    with c2:
        ats = analysis.get('ats_report', {})
        st.metric("ATS Match Score", f"{ats.get('score', 0)}%")
        st.write("**Missing Skills:**")
        for s in ats.get('missing_skills', []): st.caption(f"❌ {s}")

    st.divider()
    st.subheader("Tailored Cover Letter")
    h_score = analysis.get('humanization_score', 0)
    st.write(f"**Humanization Level:** {h_score}%")
    st.progress(h_score/100)
    st.text_area("Cover Letter", analysis.get('cover_letter', 'N/A'), height=400)

def render_applied_resume(details):
    st.subheader("Resume Used")
    available_resumes = st.session_state.get('resumes', {})
    search_kw = details.get('Found_job', '')

    matched_resume = None
    if search_kw in available_resumes:
        matched_resume = available_resumes[search_kw]
    elif available_resumes:
        matched_resume = list(available_resumes.values())[0]

    if matched_resume:
        if matched_resume.get('bytes'):
            b64_pdf = base64.b64encode(matched_resume['bytes']).decode('utf-8')
            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)
        else:
            st.text_area("Resume Content", matched_resume.get('text', ''), height=400)
    else:
        st.warning("Original resume for this application not found in session.")

def render_prep_chat(job_id, details, analysis, db):
    st.subheader("Interview Prep Guide")
    if 'qna_history' not in analysis: analysis['qna_history'] = []

    for msg in analysis['qna_history']:
        with st.chat_message(msg["role"]): st.write(msg["content"])

    q = st.chat_input("Ask a question about this job...")
    if q:
        analysis['qna_history'].append({"role": "user", "content": q})
        with st.spinner("Guide is thinking..."):
            llm = get_llm()
            jd = details.get('Job Description') or details.get('Rich Description') or "No JD."
            context = f"Job: {details.get('Job Title')} @ {details.get('Company')}\nJD: {jd}"
            prompt = f"{context}\n\nUser Question: {q}\n\nInterview Prep Guide Answer:"
            ans = llm.invoke(prompt).content
            analysis['qna_history'].append({"role": "assistant", "content": ans})

        db.save_applied(job_id, details, analysis, "applied")
        st.rerun()
