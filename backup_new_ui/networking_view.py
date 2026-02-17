import streamlit as st
from job_hunter.scrapers.linkedin_outreach import LinkedInOutreach

def render_networking_view():
    st.title("🤝 Networking & Outreach")
    st.info("Directly message your LinkedIn connections for referrals or introductions.")

    with st.form("outreach_form"):
        keyword = st.text_input("Role Keyword", placeholder="e.g. Hiring Manager")
        limit = st.number_input("Limit", min_value=1, max_value=20, value=5)
        message_template = st.text_area("Message Template", "Hi {name}, I noticed you're at {company}...")

        if st.form_submit_button("Start Outreach"):
            outreach = LinkedInOutreach()
            with st.spinner("Executing outreach..."):
                # outreach.run(...) - Mock for now to avoid actual browser action during refactor
                st.success("Outreach session completed!")
