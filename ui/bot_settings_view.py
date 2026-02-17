import streamlit as st
from job_hunter.data_manager import DataManager

def render_bot_settings_view():
    st.title("⚙️ Bot Settings")
    st.caption("Configure auto-answers for LinkedIn Easy Apply questions. Unknown questions are logged here.")

    db = DataManager()
    bot_config = db.load_bot_config()
    answers = bot_config.get("answers", {})
    unknown = bot_config.get("unknown_questions", [])

    # Stats
    c1, c2 = st.columns(2)
    c1.metric("📝 Configured Answers", len(answers))
    c2.metric("❓ Unknown Questions", len(unknown))

    st.divider()

    # Tab layout
    tab_answers, tab_unknown, tab_add = st.tabs(["📝 My Answers", "❓ Unknown Questions", "➕ Add New"])

    with tab_answers:
        st.subheader("Current Question-Answer Mappings")

        if answers:
            search_ans = st.text_input("🔍 Search answers...", key="search_answers", placeholder="Type to filter...")
            filtered_answers = {k: v for k, v in answers.items() if search_ans.lower() in k.lower() or search_ans.lower() in v.lower()} if search_ans else answers

            st.caption(f"Showing {len(filtered_answers)} of {len(answers)} answers")

            for i, (question, answer) in enumerate(list(filtered_answers.items())):
                with st.container():
                    c_q, c_a, c_del = st.columns([3, 2, 1])
                    c_q.markdown(f"**{question}**")
                    new_ans = c_a.text_input("Answer", value=answer, key=f"ans_pg_{i}", label_visibility="collapsed")

                    if new_ans != answer:
                        db.add_answer(question, new_ans)
                        st.toast(f"Updated: '{question}'")

                    if c_del.button("🗑️", key=f"del_pg_{i}"):
                        db.delete_answer(question)
                        st.rerun()
        else:
            st.info("No answers configured yet.")

    with tab_unknown:
        st.subheader("Unknown Questions Encountered")

        if unknown:
            for j, uq in enumerate(unknown):
                q_text = uq.get("question", "")
                with st.container():
                    st.markdown(f"### {j+1}. {q_text}")
                    st.caption(f"📍 From: {uq.get('job_title', '')} @ {uq.get('company', '')}")

                    c_input, c_save = st.columns([4, 1])
                    new_answer = c_input.text_input("Your Answer", key=f"uq_pg_{j}")

                    if c_save.button("💾 Save", key=f"uq_save_pg_{j}", type="primary"):
                        if new_answer:
                            db.add_answer(q_text, new_answer)
                            st.rerun()
                    st.divider()

            if st.button("🧹 Clear All Unknown Questions"):
                db.clear_unknown_questions()
                st.rerun()
        else:
            st.success("✅ No unknown questions!")

    with tab_add:
        st.subheader("Add New Mapping")
        c_q, c_a = st.columns([3, 2])
        new_q = c_q.text_input("Question Pattern", key="add_q")
        new_a = c_a.text_input("Answer", key="add_a")

        if st.button("➕ Add Answer", type="primary"):
            if new_q and new_a:
                db.add_answer(new_q, new_a)
                st.rerun()
