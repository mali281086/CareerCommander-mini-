import streamlit as st
import os
from job_hunter.data_manager import DataManager
from tools.browser_manager import BrowserManager
from ui.utils import navigate_to

def render_sidebar():
    db = DataManager()

    with st.sidebar:
        st.image("Logo.png", width=200) if os.path.exists("Logo.png") else st.title("🚀 CareerCommander")
        st.markdown("---")

        # --- BOT SETUP ---
        with st.expander("🛠️ Bot Setup (Login)", expanded=False):
            st.info("Log in manually to platforms once to save session.")
            c_open, c_close = st.columns(2)
            if c_open.button("🔓 Open Browser", width="stretch"):
                driver = BrowserManager().get_driver(headless=False)
                urls = [
                    "https://www.linkedin.com/login",
                    "https://www.xing.com/signin",
                    "https://www.stepstone.de/kandidat/login",
                    "https://www.ziprecruiter.com/login",
                ]
                driver.get(urls[0])
                for url in urls[1:]:
                    driver.execute_script(f"window.open('{url}', '_blank');")
                st.toast("✅ Browser opened! Please log in, then close this expander.")

            if c_close.button("🔒 Close Browser", width="stretch"):
                BrowserManager().close_driver()
                st.toast("Browser Closed.")

        st.markdown("### 🧠 AI Brain Settings")
        saved_keys = db.load_api_keys()
        key_options = ["Select Key..."] + list(saved_keys.keys()) + ["➕ Add New Key"]

        if 'active_gemini_key_alias' not in st.session_state:
            st.session_state['active_gemini_key_alias'] = "Select Key..."

        selected_alias = st.selectbox("Select API Key", key_options,
                                    index=key_options.index(st.session_state['active_gemini_key_alias']) if st.session_state['active_gemini_key_alias'] in key_options else 0)

        if selected_alias == "➕ Add New Key":
            with st.form("add_key_form"):
                new_alias = st.text_input("Key Alias")
                new_key = st.text_input("Gemini API Key", type="password")
                if st.form_submit_button("Save Key") and new_alias and new_key:
                    db.save_api_key(new_alias, new_key)
                    st.session_state['active_gemini_key_alias'] = new_alias
                    st.rerun()
        elif selected_alias != "Select Key...":
            active_key = saved_keys[selected_alias]
            os.environ["GOOGLE_API_KEY"] = active_key
            st.session_state['active_gemini_key_alias'] = selected_alias
            st.success(f"Connected: {selected_alias}")

            if st.button("🗑️ Delete Key"):
                db.delete_api_key(selected_alias)
                st.session_state['active_gemini_key_alias'] = "Select Key..."
                st.rerun()

        os.environ["CHOSEN_PROVIDER"] = "Google Gemini"
        st.session_state['api_provider'] = "Google Gemini"

        st.divider()
        st.markdown("### 🌐 Browser LLM Settings")
        browser_provider = st.selectbox("Browser LLM Provider", ["ChatGPT", "Gemini", "Copilot"], index=0)
        os.environ["BROWSER_LLM_PROVIDER"] = browser_provider
        st.session_state['use_browser_analysis'] = st.toggle("Use Browser for Analysis", value=True)

        st.divider()
        st.markdown("#### Navigation")
        if st.button("🏠 Home", use_container_width=True): navigate_to('home')
        if st.button("📋 Current Job Batch", use_container_width=True): navigate_to('explorer')
        if st.button("📂 View Applied Jobs", use_container_width=True): navigate_to('applied')
        if st.button("🤝 Networking", use_container_width=True): navigate_to('networking')
        if st.button("⚙️ Bot Settings", use_container_width=True): navigate_to('bot_settings')

        st.divider()
        st.markdown("<div style='text-align: center; font-size: 0.8em; color: gray;'>Designed by <b>TAM Inc.</b></div>", unsafe_allow_html=True)
