import streamlit as st

def render_settings_view(db):
    st.title("⚙️ Bot Settings")
    st.caption("Configure auto-answers for LinkedIn Easy Apply questions. Unknown questions are logged here.")

    bot_config = db.load_bot_config()
    answers = bot_config.get("answers", {})
    unknown = bot_config.get("unknown_questions", [])

    # Stats
    c1, c2 = st.columns(2)
    c1.metric("📝 Configured Answers", len(answers))
    c2.metric("❓ Unknown Questions", len(unknown))

    st.divider()

    # Tab layout
    tab_answers, tab_unknown, tab_add, tab_selectors = st.tabs(["📝 My Answers", "❓ Unknown Questions", "➕ Add New", "🛠️ Advanced Selectors"])

    with tab_answers:
        st.subheader("Current Question-Answer Mappings")

        if answers:
            # Search within answers
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
                        st.toast(f"Updated: '{question}' → '{new_ans}'")
                        st.rerun()

                    if c_del.button("🗑️", key=f"del_pg_{i}", help="Delete this answer"):
                        db.delete_answer(question)
                        st.toast(f"Deleted: '{question}'")
                        st.rerun()
        else:
            st.info("No answers configured yet. Add some in the 'Add New' tab!")

    with tab_unknown:
        st.subheader("Unknown Questions Encountered")

        if unknown:
            st.warning(f"**{len(unknown)} question(s)** the bot couldn't answer. Add your answers below!")

            for j, uq in enumerate(unknown):
                q_text = uq.get("question", "")
                job_info = f"{uq.get('job_title', '')} @ {uq.get('company', '')}" if uq.get('job_title') else ""
                timestamp = uq.get("timestamp", "")

                with st.container():
                    st.markdown(f"### {j+1}. {q_text}")
                    if job_info:
                        st.caption(f"📍 From: {job_info}")
                    if timestamp:
                        st.caption(f"🕐 {timestamp[:10]}")

                    c_input, c_save = st.columns([4, 1])
                    new_answer = c_input.text_input("Your Answer", key=f"uq_pg_{j}", placeholder="Enter your answer for this question...")

                    if c_save.button("💾 Save", key=f"uq_save_pg_{j}", type="primary"):
                        if new_answer:
                            db.add_answer(q_text, new_answer)
                            st.toast(f"✅ Added answer for '{q_text}'")
                            st.rerun()
                        else:
                            st.error("Please enter an answer")

                    st.divider()

            if st.button("🧹 Clear All Unknown Questions", type="secondary"):
                db.clear_unknown_questions()
                st.toast("Cleared all unknown questions")
                st.rerun()
        else:
            st.success("✅ No unknown questions! The bot has answers for all encountered questions.")

    with tab_add:
        st.subheader("Add New Question-Answer Mapping")

        c_q, c_a = st.columns([3, 2])
        new_q = c_q.text_input("Question Pattern", placeholder="e.g. 'years of experience'", key="add_q_pg")
        new_a = c_a.text_input("Answer", placeholder="e.g. '5'", key="add_a_pg")

        if st.button("➕ Add Answer", type="primary"):
            if new_q and new_a:
                db.add_answer(new_q, new_a)
                st.toast(f"✅ Added: '{new_q}' → '{new_a}'")
                st.rerun()
            else:
                st.error("Please enter both question pattern and answer")

    with tab_selectors:
        st.subheader("🛠️ CSS/XPath Selectors Configuration")
        st.caption("Customize the selectors used by the bot to interact with job boards. Only modify if you know what you are doing!")

        selectors_dict = db.load_selectors()
        import yaml

        selectors_yaml = yaml.dump(selectors_dict, default_flow_style=False)

        # YAML Editor
        new_selectors_yaml = st.text_area("Selectors (YAML Format)", value=selectors_yaml, height=500)

        if st.button("💾 Save Selectors", type="primary"):
            try:
                new_selectors_dict = yaml.safe_load(new_selectors_yaml)
                db.save_selectors(new_selectors_dict)
                st.success("✅ Selectors updated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to save selectors: {e}")
