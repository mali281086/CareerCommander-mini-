import streamlit as st
import time
import random

def render_networking_view():
    st.title("🤝 LinkedIn Networking Outreach")
    st.write("Connect with your existing LinkedIn contacts in specific regions.")

    with st.container(border=True):
        st.subheader("1. Setup Outreach")
        outreach_loc = st.text_input("Target Region/Location", value="Germany")
        outreach_limit = st.number_input("Max Contacts to Message", value=5, min_value=1, max_value=20)

        default_msg = "Hi {first_name},\n\nI hope you are doing well. I am currently exploring new opportunities in the job market and noticed you are based in {location}. I was wondering if you might have any leads or advice for someone with my background. Any assistance would be greatly appreciated!\n\nBest regards,"
        outreach_msg = st.text_area("Message Template", value=default_msg.replace("{location}", outreach_loc), height=200, help="Use {first_name} as a placeholder.")

    if st.button("🔍 Find and Message Contacts", type="primary"):
        from job_hunter.scrapers.linkedin_outreach import LinkedInOutreach
        outreach = LinkedInOutreach()

        try:
            status_box = st.empty()
            status_box.info(f"Searching for 1st-degree connections in **{outreach_loc}**...")

            connections = outreach.search_connections(outreach_loc, limit=outreach_limit)

            if not connections:
                status_box.warning("No connections found for the given criteria. Make sure you are logged in to LinkedIn.")
            else:
                status_box.success(f"Found {len(connections)} connections. Starting outreach...")

                progress_bar = st.progress(0)
                for i, conn in enumerate(connections):
                    status_box.info(f"Sending message to **{conn['name']}** ({i+1}/{len(connections)})...")
                    success = outreach.send_message(conn, outreach_msg)
                    if success:
                        st.toast(f"✅ Message sent to {conn['name']}")
                    else:
                        st.error(f"❌ Failed to send message to {conn['name']}")

                    progress_bar.progress((i + 1) / len(connections))
                    time.sleep(random.uniform(2, 5))

                status_box.success("🎉 Outreach mission complete!")

        except Exception as e:
            st.error(f"An error occurred: {e}")
        finally:
            outreach.close()
