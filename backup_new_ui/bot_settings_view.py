import streamlit as st
from job_hunter.data_manager import DataManager

def render_bot_settings_view():
    st.title("⚙️ Bot Settings")
    db = DataManager()

    bot_config = db.load_bot_config()
    answers = bot_config.get("answers", {})
    unknown = bot_config.get("unknown_questions", [])

    c1, c2 = st.columns(2)
    c1.metric("📝 Configured Answers", len(answers))
    c2.metric("❓ Unknown Questions", len(unknown))

    tab_answers, tab_unknown, tab_add = st.tabs(["📝 My Answers", "❓ Unknown Questions", "➕ Add New"])

    with tab_answers:
        st.subheader("Current Mappings")
        search_ans = st.text_input("🔍 Search...", placeholder="Filter questions or answers")

        items = list(answers.items())
        if search_ans:
            items = [(k, v) for k, v in items if search_ans.lower() in k.lower() or search_ans.lower() in v.lower()]

        for i, (q, a) in enumerate(items):
            with st.container():
                col_q, col_a, col_d = st.columns([3, 2, 1])
                col_q.markdown(f"**{q}**")
                new_v = col_a.text_input("Answer", value=a, key=f"ans_{i}", label_visibility="collapsed")
                if new_v != a:
                    db.add_answer(q, new_v)
                    st.toast(f"Updated {q}")
                if col_d.button("🗑️", key=f"del_{i}"):
                    db.delete_answer(q)
                    st.rerun()

    with tab_unknown:
        st.subheader("Unknown Questions")
        if not unknown:
            st.success("No unknown questions! You are all set.")
        else:
            for j, uq in enumerate(unknown):
                st.markdown(f"**{uq.get('question')}**")
                st.caption(f"📍 {uq.get('job_title')} @ {uq.get('company')}")
                col_i, col_s = st.columns([4, 1])
                new_a = col_i.text_input("Answer", key=f"uq_{j}")
                if col_s.button("💾 Save", key=f"uqs_{j}"):
                    if new_a:
                        db.add_answer(uq.get('question'), new_a)
                        st.rerun()
            if st.button("🧹 Clear All"):
                db.clear_unknown_questions()
                st.rerun()

    with tab_add:
        st.subheader("Add Mapping")
        new_q = st.text_input("Question Pattern")
        new_a = st.text_input("Value")
        if st.button("Add"):
            if new_q and new_a:
                db.add_answer(new_q, new_a)
                st.rerun()
