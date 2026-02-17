import streamlit as st
import base64
from job_hunter.data_manager import DataManager
from job_hunter.model_factory import get_llm

def render_applied_view():
    st.title("📂 Applied Jobs")
    db = DataManager()
    applied = db.load_applied()

    if not applied:
        st.info("No applied jobs yet.")
        return

    job_ids = list(applied.keys())
    selected_id = st.selectbox("Select a job", job_ids)

    if selected_id:
        record = applied[selected_id]
        details = record.get('job_details', {})
        analysis = record.get('ai_analysis', {})

        st.subheader(f"{details.get('title')} @ {details.get('company')}")
        st.caption(f"Applied on: {record.get('created_at')}")

        t1, t2, t3 = st.tabs(["📊 Analysis", "📄 Resume & Persona", "💬 Chat"])

        with t1:
            st.markdown(analysis.get('intel', 'N/A'))
            with st.expander("Show Cover Letter"):
                st.code(analysis.get('cover_letter', 'N/A'))

        with t2:
            st.write("Persona used for this application.")
            # ... Resume display logic ...
            st.info("Resume visualization is currently available for active personas.")

        with t3:
            st.subheader("Interview Guide Chat")
            if 'qna_history' not in record: record['qna_history'] = []

            for msg in record['qna_history']:
                with st.chat_message(msg["role"]): st.write(msg["content"])

            q = st.chat_input("Ask about this job...")
            if q:
                record['qna_history'].append({"role": "user", "content": q})
                with st.spinner("Thinking..."):
                    llm = get_llm()
                    prompt = f"Job: {details}\nQuestion: {q}\nAI Guide Answer:"
                    ans = llm.invoke(prompt).content
                    record['qna_history'].append({"role": "assistant", "content": ans})
                db.save_applied(selected_id, details, record.get('ai_analysis'), record.get('status'))
                st.rerun()
