import streamlit as st
import time
import random

def render_networking_view():
    st.title("🤝 LinkedIn Networking Outreach")
    st.write("Connect with your existing LinkedIn contacts in specific regions.")

    with st.container(border=True):
        st.subheader("1. Setup Outreach")
        outreach_loc = st.text_input("Target Region/Location", value="Germany", help="LinkedIn will search for 1st-degree connections in this location.")
        outreach_limit = st.number_input("Max Contacts to Process", value=1, min_value=1, max_value=20, help="For testing, start with 1.")

        st.info("💡 The bot will skip contacts you have already messaged in previous runs.")

        # Resume Integration
        resumes = st.session_state.get('resumes', {})
        if resumes:
            selected_resume = st.selectbox("Select Resume for Context", options=["None"] + list(resumes.keys()))
            if selected_resume != "None":
                if st.button("🪄 Generate Message from Resume"):
                    from job_hunter.career_advisor import CareerAdvisor
                    advisor = CareerAdvisor()
                    with st.spinner("Generating short message..."):
                        resume_text = resumes[selected_resume].get('text', '')
                        generated = advisor.generate_outreach_message(resume_text)
                        if generated:
                            st.session_state['outreach_msg_template'] = generated
                            st.rerun()
                    advisor.close()

        default_msg = "Hi {first_name},\n\nI hope you are doing well. I'm currently looking for new projects or job matches that fit my credentials and I noticed you're in my network. If you know of any matching opportunities, I'd appreciate a heads up!\n\nBest regards,"

        # Use session state to persist generated message across reruns
        if 'outreach_msg_template' not in st.session_state:
            st.session_state['outreach_msg_template'] = default_msg

        outreach_msg = st.text_area("Message Template", value=st.session_state['outreach_msg_template'], height=200, help="Use {first_name} or {name} as placeholders.")

        # Sync back to session state if edited manually
        st.session_state['outreach_msg_template'] = outreach_msg

        auto_send = st.checkbox("Auto-send messages (Clicking 'Send' on LinkedIn)", value=False, help="Keep this UNCHECKED to review messages before sending manually.")

    if st.button("🔍 Start Outreach Mission", type="primary"):
        from job_hunter.scrapers.linkedin_outreach import LinkedInOutreach
        outreach = LinkedInOutreach()

        try:
            status_box = st.empty()
            status_box.info(f"Searching for 1st-degree connections in **{outreach_loc}**...")

            connections = outreach.search_connections(outreach_loc, limit=outreach_limit)

            if not connections:
                status_box.warning("No connections found for the given criteria (or everyone has already been messaged).")
            else:
                status_box.success(f"Found {len(connections)} new connections. Processing...")

                progress_bar = st.progress(0)
                for i, conn in enumerate(connections):
                    action_text = "Sending" if auto_send else "Preparing"
                    status_box.info(f"{action_text} message for **{conn['name']}** ({i+1}/{len(connections)})...")

                    success = outreach.send_message(conn, outreach_msg, auto_send=auto_send)

                    if success:
                        result_text = "Sent" if auto_send else "Prepared (Review on LinkedIn)"
                        st.toast(f"✅ Message {result_text} for {conn['name']}")
                    else:
                        st.error(f"❌ Failed to process {conn['name']}")

                    progress_bar.progress((i + 1) / len(connections))
                    if i < len(connections) - 1:
                        time.sleep(random.uniform(3, 6))

                status_box.success("🎉 Outreach mission complete! The browser will stay open for your review.")

        except Exception as e:
            st.error(f"An error occurred: {e}")
        finally:
            outreach.close()
