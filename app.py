import os
# Must be set BEFORE importing crewai to avoid Telemetry/Signal errors
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

import streamlit as st
import pandas as pd
import json
import glob
import base64
import time
import random
from datetime import datetime
from dotenv import load_dotenv

# Load other envs
# Load other envs
load_dotenv()

# --- METRICS DASHBOARD HELPERS ---
def render_metrics_dashboard(current_df, applied_dict, parked_count=0):
    """
    Renders Dashboard 2.1: Cards on Top, Stacked Timeline, Toggle-only.
    """
    import altair as alt

    # --- 0. PRE-PROCESSING ---
    
    # Ensure current_df has 'Found_job'
    if not current_df.empty and 'Found_job' not in current_df.columns:
        current_df['Found_job'] = "Unknown"
    
    # Convert Applied Dict to DataFrame
    applied_rows = []
    for jid, data in applied_dict.items():
        details = data.get('job_details', {})
        applied_rows.append({
            "Platform": details.get('Platform', 'Unknown'),
            "Found_job": details.get('Found_job', 'Unknown'),
            "created_at": data.get('created_at', datetime.now().isoformat())
        })
    applied_df = pd.DataFrame(applied_rows)

    # --- 1. METRICS (Displayed FIRST) ---
    
    # Calc Counts (Global)
    count_scouted = len(current_df)
    count_applied = len(applied_df)
    count_total = count_scouted + count_applied
    
    # Calc Avg Applied / Day
    avg_msg = "N/A"
    avg_val = 0.0
    if not applied_df.empty:
        dates = pd.to_datetime(applied_df['created_at'])
        first_date = dates.min()
        last_date = datetime.now()
        # Fix: inclusive days span
        days_diff = (last_date.date() - first_date.date()).days + 1
        if days_diff < 1: days_diff = 1 
        
        total_applied_global = len(applied_df)
        avg_val = total_applied_global / days_diff
        avg_msg = f"{avg_val:.1f}"

    # Custom HTML for Centered Metrics
    def card(label, value, help_text=""):
        return f"""
        <div style="
            background-color: #262730; 
            padding: 20px; 
            border-radius: 10px; 
            border: 1px solid #41424C;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.2);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        ">
            <p style="font-size: 0.9em; color: #aaaaaa; margin: 0 0 5px 0;">{label}</p>
            <h2 style="margin: 0; padding: 0; font-size: 2em; color: white; text-align: center;">{value}</h2>
        </div>
        """
        
        
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: st.markdown(card("Current Jobs", count_scouted), unsafe_allow_html=True)
    with m2: st.markdown(card("Applied Jobs", count_applied), unsafe_allow_html=True)
    with m3: st.markdown(card("Parked Jobs", parked_count), unsafe_allow_html=True)
    with m4: st.markdown(card("Total Jobs", count_total + parked_count), unsafe_allow_html=True)
    with m5: st.markdown(card("Avg job applied / day", avg_msg), unsafe_allow_html=True)

    st.markdown("###")

    # --- 2. CONTROLS (Toggle Only) ---
    c_view, _ = st.columns([1, 4])
    view_by = c_view.radio("View Charts By:", ["Target Role", "Platform"], horizontal=True, label_visibility="collapsed")
    group_col = "Found_job" if view_by == "Target Role" else "Platform"

    # --- 3. PIE CHARTS ---
    st.markdown("##### Distribution")
    
    # Prepare Data
    if not current_df.empty:
        curr_counts = current_df[group_col].fillna("Unknown").value_counts().reset_index()
        curr_counts.columns = ['Label', 'Count']
    else: curr_counts = pd.DataFrame(columns=['Label', 'Count'])
    
    if not applied_df.empty:
        app_counts = applied_df[group_col].fillna("Unknown").value_counts().reset_index()
        app_counts.columns = ['Label', 'Count']
    else: app_counts = pd.DataFrame(columns=['Label', 'Count'])

    c_chart1, c_chart2 = st.columns(2)
    
    # Chart 1: Current
    with c_chart1:
        st.caption(f"Current Jobs ({view_by})")
        if not curr_counts.empty:
            curr_counts['Percent'] = (curr_counts['Count'] / curr_counts['Count'].sum()).apply(lambda x: f"{x:.1%}")
            
            base = alt.Chart(curr_counts).encode(theta=alt.Theta("Count", stack=True))
            pie = base.mark_arc(outerRadius=100, innerRadius=60).encode(
                color=alt.Color("Label", title=view_by),
                order=alt.Order("Count", sort="descending"),
                tooltip=["Label", "Count", "Percent"]
            )
            text = base.mark_text(radius=120).encode(
                text="Percent",
                order=alt.Order("Count", sort="descending"),
                color=alt.value("white") 
            )
            st.altair_chart(pie + text, width="stretch")
        else:
            st.info("No data.")

    # Chart 2: Applied
    with c_chart2:
        st.caption(f"Applied Jobs ({view_by})")
        if not app_counts.empty:
            app_counts['Percent'] = (app_counts['Count'] / app_counts['Count'].sum()).apply(lambda x: f"{x:.1%}")
            
            base = alt.Chart(app_counts).encode(theta=alt.Theta("Count", stack=True))
            pie = base.mark_arc(outerRadius=100, innerRadius=60).encode(
                color=alt.Color("Label", title=view_by),
                order=alt.Order("Count", sort="descending"),
                tooltip=["Label", "Count", "Percent"]
            )
            text = base.mark_text(radius=120).encode(
                text="Percent",
                order=alt.Order("Count", sort="descending"),
                color=alt.value("white") 
            )
            st.altair_chart(pie + text, width="stretch")
        else:
            st.info("No data.")
            
    # --- 4. STACKED BAR CHART (Timeline) ---
    st.markdown(f"##### Application Timeline (Total: {count_applied})")
    if not applied_df.empty:
        # Pre-process
        timeline_df = applied_df.copy()
        timeline_df['Date'] = pd.to_datetime(timeline_df['created_at']).dt.date.astype(str)
        
        # Group by Date AND the selected Dimension (group_col)
        # We count occurrences
        daily_counts = timeline_df.groupby(['Date', group_col]).size().reset_index(name='Count')
        
        # Base Chart
        base = alt.Chart(daily_counts).encode(x=alt.X('Date', title='Date'))
        
        # Bars
        bars = base.mark_bar().encode(
            y=alt.Y('Count', title='Jobs Applied'),
            color=alt.Color(group_col, title=view_by),
            tooltip=['Date', group_col, 'Count']
        )
        
        # Text Labels (Sum per day)
        text = base.mark_text(dy=-10).encode(
            y=alt.Y('sum(Count)', stack=True),
            text=alt.Text('sum(Count)'),
            color=alt.value('white')  # Ensure visibility
        )
        
        st.altair_chart((bars + text).interactive(), width="stretch")
    else:
        st.info("No application history to show timeline.")

    st.divider()

from job_hunter.analysis_crew import JobAnalysisCrew
from job_hunter.resume_parser import parse_resume
from job_hunter.career_advisor import CareerAdvisor
from job_hunter.data_manager import DataManager
from job_hunter.model_factory import validate_api_key, get_available_models # Factory

# --- Config ---
# Page Config
st.set_page_config(page_title="CareerCommander", layout="wide", page_icon="🚀")

# Initialize Data Manager (Global)
db = DataManager()

def navigate_to(page):
    st.session_state['page'] = page
    st.rerun()

# Sidebar
with st.sidebar:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("Logo.png", width=120)

    # --- BOT SETUP (Legacy Login) ---
    with st.expander("🛠️ Bot Setup (Login)", expanded=False):
        st.caption("Open browser to log in to LinkedIn, Indeed, etc. manually.")
        
        c_open, c_close = st.columns(2)
        if c_open.button("🔓 Open"):
            from tools.browser_manager import BrowserManager
            bm = BrowserManager()
            driver = bm.get_driver(headless=False)
            # Open all platforms in tabs
            urls = [
                "https://www.linkedin.com/login",
                "https://secure.indeed.com/account/login",
                "https://www.stepstone.de/login",
                "https://login.xing.com/",
                "https://www.ziprecruiter.com/login"
            ]
            
            # First tab
            driver.get(urls[0])
            
            # Others
            for url in urls[1:]:
                driver.execute_script(f"window.open('{url}', '_blank');")
            
            st.toast("Opened 5 Login Tabs! Please log in to all of them.")
            
        if c_close.button("🔒 Close"):
            from tools.browser_manager import BrowserManager
            BrowserManager().close_driver()
            st.toast("Browser Closed.")
    
    st.markdown("### 🧠 AI Brain Settings (Gemini Only)")
    
    # 1. API Key Manager
    saved_keys = db.load_api_keys()
    
    # Dropdown for selecting key
    key_options = ["Select Key..."] + list(saved_keys.keys()) + ["➕ Add New Key"]
    
    # Initialize connection state
    if 'active_gemini_key_alias' not in st.session_state: 
        # Try to find a default or previously used
        st.session_state['active_gemini_key_alias'] = "Select Key..."
        
    selected_alias = st.selectbox("Select API Key", key_options, index=key_options.index(st.session_state['active_gemini_key_alias']) if st.session_state['active_gemini_key_alias'] in key_options else 0)
    
    if selected_alias == "➕ Add New Key":
        with st.form("add_key_form"):
            new_alias = st.text_input("Key Alias (e.g. 'Personal', 'Work')")
            new_key = st.text_input("Gemini API Key", type="password")
            submitted = st.form_submit_button("Save Key")
            if submitted and new_alias and new_key:
                db.save_api_key(new_alias, new_key)
                st.session_state['active_gemini_key_alias'] = new_alias
                st.toast(f"Key '{new_alias}' saved!")
                st.rerun()
    elif selected_alias != "Select Key...":
        # Set Active Key
        active_key = saved_keys[selected_alias]
        os.environ["GOOGLE_API_KEY"] = active_key
        st.session_state['active_gemini_key_alias'] = selected_alias
        
        # Validation / Model Selection
        if active_key:
            validate_api_key(active_key, "Google Gemini")
            # Fetch Models
            try:
                models = get_available_models("Google Gemini", active_key)
                if models:
                    idx = models.index("gemini-1.5-flash") if "gemini-1.5-flash" in models else 0
                    model_name = st.selectbox("Select Model", models, index=idx)
                else:
                    model_name = st.text_input("Model Name", value="gemini-1.5-flash")
            except:
                model_name = st.text_input("Model Name", value="gemini-1.5-flash")
            
            if model_name: os.environ["CHOSEN_MODEL"] = model_name
            
            # Show active status
            st.success(f"Connected: {selected_alias}")
            
            # Delete Option
            if st.button("🗑️ Delete Key", key="del_api_key"):
                db.delete_api_key(selected_alias)
                st.session_state['active_gemini_key_alias'] = "Select Key..."
                st.rerun()

    # Force Provider to Gemini
    os.environ["CHOSEN_PROVIDER"] = "Google Gemini"
    st.session_state['api_provider'] = "Google Gemini"

    st.divider()
    
    # --- NAVIGATION ---
    st.markdown("#### Pages for navigation")
    if st.button("🏠 Home", width="stretch"):
        st.session_state['page'] = 'home'
        st.rerun()
        
    if st.button("📋 Current Job Batch", width="stretch"):
         navigate_to('explorer')
         
    if st.button("📂 View Applied Jobs", width="stretch"):
         navigate_to('applied')

    if st.button("🤝 Networking", width="stretch"):
         navigate_to('networking')
    
    if st.button("⚙️ Bot Settings", width="stretch"):
         navigate_to('bot_settings')
         
    st.divider()
    st.markdown(
        """
        <div style="text-align: center; font-size: 0.8em; color: gray;">
            This product is designed by <b>TAM Inc.</b><br>
            Powered by Gemini, Streamlit & more.
        </div>
        """, 
        unsafe_allow_html=True
    )


# --- Session State Init ---
if 'page' not in st.session_state: st.session_state['page'] = 'home'
# RESUMES DICT: { "Role Name": { "filename": "x.pdf", "text": "...", "bytes": b"..." } }
if 'resumes' not in st.session_state: st.session_state['resumes'] = {}
# Legacy fallback (keep for now to avoid break, but code should prioritize 'resumes')
if 'resume_text' not in st.session_state: st.session_state['resume_text'] = "" 
if 'suggestions' not in st.session_state: st.session_state['suggestions'] = []
# Default scraper settings (global or per resume?) -> Global for now, keywords derived from Resumes
if 'scrape_location' not in st.session_state: st.session_state['scrape_location'] = "Germany"
if 'analyzed_job_id' not in st.session_state: st.session_state['analyzed_job_id'] = None
if 'analysis_results' not in st.session_state: st.session_state['analysis_results'] = {}

# --- Config & Helper Functions for Persistence ---
RESUME_DIR = os.path.join("data", "resumes")
RESUME_CONFIG = os.path.join("data", "resume_config.json")
os.makedirs(RESUME_DIR, exist_ok=True)

def save_resume_config():
    """Save current resumes config to disk."""
    config_data = {}
    for role, data in st.session_state['resumes'].items():
        # Exclude bytes, store path and text
        config_data[role] = {
            "filename": data.get("filename"),
            "file_path": data.get("file_path"),
            "text": data.get("text"),
            "suggestions": data.get("suggestions", [])
        }
    try:
        with open(RESUME_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
    except Exception as e:
        print(f"Error saving resume config: {e}")

def load_resume_config():
    """Load resumes from disk into session state."""
    if os.path.exists(RESUME_CONFIG):
        try:
            with open(RESUME_CONFIG, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            
            for role, data in config_data.items():
                fpath = data.get("file_path")
                if fpath and os.path.exists(fpath):
                    # Load bytes
                    with open(fpath, "rb") as f:
                        file_bytes = f.read()
                    
                    st.session_state['resumes'][role] = {
                        "filename": data.get("filename"),
                        "file_path": fpath,
                        "text": data.get("text", ""),
                        "bytes": file_bytes,
                        "suggestions": data.get("suggestions", [])
                    }
        except Exception as e:
            print(f"Error loading resume config: {e}")

# Load on Startup if dict is empty
if not st.session_state.get('resumes'):
    load_resume_config()

# Initialize Data Manager
# db = DataManager() # Moved to top
# Load Cache into Session State
if 'job_cache' not in st.session_state:
    st.session_state['job_cache'] = db.load_cache()
if 'applied_jobs' not in st.session_state:
    st.session_state['applied_jobs'] = db.load_applied()

# --- Helper Functions ---
@st.cache_data
def load_data():
    db = DataManager()
    data = db.load_scouted()
    if not data: return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Normalize Columns for UI
    # Scraper gives: title, company, location, link, platform
    # UI expects: Job Title, Company, Location, Web Address, Platform
    rename_map = {
        "title": "Job Title",
        "company": "Company",
        "location": "Location",
        "link": "Web Address",
        "platform": "Platform",
        "description": "Job Description",
        "rich_description": "Rich Description",
        "language": "Language"
    }
    df = df.rename(columns=rename_map)
    
    # Explicitly drop legacy columns if they exist in the loaded data
    cols_to_drop = ["location_actual", "posted_date"]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors='ignore')
    
    # Ensure required columns exist
    required = ["Job Title", "Company", "Location", "Web Address", "Platform", "Found_job"]
    for col in required:
        if col not in df.columns:
            df[col] = "Unknown"
            
    return df



def mark_as_applied(job_id, job_row, analysis_results):
    # Convert Series to dict if needed
    if isinstance(job_row, pd.Series):
        job_data = job_row.to_dict()
    else:
        job_data = job_row
        
    st.session_state['applied_jobs'] = db.save_applied(job_id, job_data, analysis_results)
    st.toast("Job synced to Application Database! 💾")

# ==========================================
# VIEW 1: COMMAND CENTER (HOME)
# ==========================================
if st.session_state['page'] == 'home':
    st.title("🎖️ CareerCommander")
    
    # --- Enforce AI Setup ---
    # --- Enforce AI Setup ---
    # Check if a key alias is selected
    if st.session_state.get('active_gemini_key_alias', "Select Key...") == "Select Key...":
        st.info("👈 **Start Here**: Please select (or add) a Google Gemini API Key in the sidebar.")
        st.stop()

    # Check if Env Var is set (Double Check)
    if not os.getenv("GOOGLE_API_KEY"):
         st.error("⚠️ Google API Key not detected in environment. Please Try selecting the key again.")
         st.stop()

    # 1. PROFILE SECTION (MULTI-RESUME)
    with st.expander("📂 Step 1: Manage Resumes & Roles", expanded=True):
        uploaded_files = st.file_uploader("Upload Resumes (PDF)", type=["pdf"], accept_multiple_files=True)
        
        # Process new uploads
        if uploaded_files:
            for up_file in uploaded_files:
                # Check if file already processed by filename matching
                already_exists = False
                for role_data in st.session_state['resumes'].values():
                   if role_data['filename'] == up_file.name: already_exists = True
                
                if not already_exists:
                    with st.spinner(f"Processing {up_file.name}..."):
                        # Save to Disk
                        save_path = os.path.join(RESUME_DIR, up_file.name)
                        with open(save_path, "wb") as f:
                            f.write(up_file.getbuffer())
                            
                        text = parse_resume(up_file)
                        if text:
                            # Manual Role Name (Default to filename)
                            default_role = up_file.name
                            
                            # Ensure unique key
                            if default_role in st.session_state['resumes']:
                                default_role = f"{default_role} ({int(time.time())})"
                                
                            st.session_state['resumes'][default_role] = {
                                "filename": up_file.name,
                                "file_path": save_path,
                                "text": text,
                                "bytes": up_file.getvalue(),
                                "suggestions": [],
                                "target_keywords": "" # Initialize empty
                            }
                            save_resume_config()
                            st.toast(f"Added: {default_role}")
        
        # Display / Edit Active Resumes
        if st.session_state['resumes']:
            st.write("### 🦸 Active Personas")
            # Convert to list to allow modification of keys
            current_roles = list(st.session_state['resumes'].keys())
            
            cols = st.columns(3)
            for i, role_key in enumerate(current_roles):
                data = st.session_state['resumes'][role_key]
                with cols[i % 3]:
                    with st.container(border=True):
                        st.caption(f"📄 {data['filename']}")
                        # Use filename as unique key
                        unique_key = f"role_edit_{data['filename']}"
                        
                        # 1. Persona Name (Display only mostly)
                        new_role_name = st.text_input("Persona Name", value=role_key, key=unique_key)
                        
                        # 2. Target Keywords (Semicolon separated)
                        # Load existing or default to Role Name if empty (legacy support)
                        current_keywords = data.get("target_keywords", "")
                        new_keywords = st.text_area("Target Role(s) (separate by ';')", value=current_keywords, height=100, key=f"kw_{unique_key}", help="e.g. Data Scientist; Data Analyst")
                        
                        # Save Keywords immediately on change (using session state persistency)
                        if new_keywords != current_keywords:
                            st.session_state['resumes'][role_key]['target_keywords'] = new_keywords
                            save_resume_config()
                        
                        # Update Key if changed
                        if new_role_name != role_key:
                             if new_role_name in st.session_state['resumes']:
                                 st.warning("Name already exists!")
                             else:
                                 st.session_state['resumes'][new_role_name] = st.session_state['resumes'].pop(role_key)
                                 save_resume_config()
                                 st.rerun() # Refresh immediately
                             
                        if st.button("🗑️ Remove", key=f"del_{data['filename']}"):
                            del st.session_state['resumes'][new_role_name]
                            save_resume_config()
                            st.rerun()

    # 2. MISSION CONFIGURATION (BATCH)
    st.divider()
    st.subheader("Step 2: Mission Configuration")
    
    with st.container(border=True):
        if not st.session_state['resumes']:
             st.warning("⚠️ Please upload at least one resume in Step 1.")
        else:
             st.info(f"Ready to launch missions for {len(st.session_state['resumes'])} Target Roles.")
        
        c1, c2 = st.columns(2)
        scrape_location = c1.text_input("Target Location(s) (separate by ';')", value=st.session_state.get('scrape_location', "Germany"), help="e.g. Berlin; Munich; Hamburg")
        st.session_state['scrape_location'] = scrape_location
        
        scrape_limit = c2.number_input("Limit per Role & Platform", value=30, step=10, min_value=1, max_value=5000)
        
        c_easy, c_ph = st.columns([1, 1])
        easy_apply_only = c_easy.toggle("✨ Easy Apply Only", value=False, help="Full Auto Mode: Browse & Apply until target is reached")
        
        if easy_apply_only:
             platforms = ["LinkedIn", "Xing"]
             # Force selection to these two
             selected_platforms = st.multiselect("Platforms", platforms, default=platforms, disabled=True, help="Restricted to platforms supporting reliable automated Easy Apply.")
             
             st.info("🤖 **Live Apply Mode**: Bot will browse job pages and apply until target is reached, skipping blacklisted/parked/applied jobs!")
             
             # Target Apply Count
             c_target, c_res, c_phone = st.columns(3)
             target_apply_count = c_target.number_input("🎯 Target Applications", value=5, min_value=1, max_value=50, step=1, help="Bot will keep applying until this many successful applications")
             
             # Resume Selection for Auto-Apply
             resume_options = list(st.session_state.get('resumes', {}).keys())
             if resume_options:
                 auto_resume_key = c_res.selectbox("Resume for Auto-Apply", resume_options, key="auto_apply_resume_home")
                 auto_resume_path = st.session_state['resumes'].get(auto_resume_key, {}).get('file_path', '')
             else:
                 c_res.warning("⚠️ No resume uploaded!")
                 auto_resume_path = ''
             
             auto_phone = c_phone.text_input("Phone Number", value="", key="auto_apply_phone_home", placeholder="+49 123 456789")
        else:
             platforms = ["LinkedIn", "Indeed", "Stepstone", "Xing", "ZipRecruiter"]
             selected_platforms = st.multiselect("Platforms", platforms, default=platforms)
             auto_resume_path = ''
             auto_phone = ''
        
        st.markdown("###")

        # ACTION BUTTONS
        col_run, col_skip = st.columns([1, 1])
        
        with col_run:
            if st.button("🚀 Launch All Missions", type="primary", width="stretch", disabled=not st.session_state['resumes']):
                status_box = st.empty()
                
                # === EASY APPLY LIVE MODE (Skip scraping entirely) ===
                if easy_apply_only and auto_resume_path:
                    status_box.info(f"🤖 **Live Apply Mode**: Targeting {target_apply_count} successful applications...")
                    
                    from job_hunter.applier import JobApplier
                    applier = JobApplier(resume_path=auto_resume_path, phone_number=auto_phone)
                    
                    total_applied = 0
                    total_skipped = 0
                    total_errors = 0
                    
                    for role_name, resume_data in st.session_state['resumes'].items():
                        if total_applied >= target_apply_count:
                            break
                            
                        # Use target_keywords (same as standard scrape mode)
                        raw_kw = resume_data.get("target_keywords", "")
                        keywords = [k.strip() for k in raw_kw.split(';') if k.strip()]
                        if not keywords:
                            # Fallback to suggestions if target_keywords is empty
                            suggestions = resume_data.get("suggestions", [])
                            if isinstance(suggestions, list) and suggestions:
                                keywords = suggestions
                            else:
                                st.warning(f"⚠️ No keywords set for '{role_name}'. Please set Target Keywords in Step 1.")
                                continue
                        
                        locations = [l.strip() for l in scrape_location.split(';') if l.strip()]
                        if not locations:
                            locations = ["Germany"]
                        
                        for kw in keywords:
                            if total_applied >= target_apply_count:
                                break
                            for loc in locations:
                                if total_applied >= target_apply_count:
                                    break
                                    
                                remaining = target_apply_count - total_applied
                                
                                # LinkedIn Live Apply
                                status_box.info(f"🔍 [LinkedIn] Searching '{kw}' in '{loc}' (need {remaining} more)...")
                                
                                try:
                                    results = applier.live_apply_linkedin(
                                        keyword=kw,
                                        location=loc,
                                        target_count=remaining
                                    )
                                    
                                    total_applied += len(results.get("applied", []))
                                    total_skipped += len(results.get("skipped", []))
                                    total_errors += len(results.get("errors", []))
                                    st.session_state['applied_jobs'] = db.load_applied()
                                    
                                except Exception as e:
                                    st.error(f"LinkedIn error: {e}")
                                
                                # Xing Live Apply (if still need more)
                                if total_applied < target_apply_count:
                                    remaining = target_apply_count - total_applied
                                    status_box.info(f"🔍 [Xing] Searching '{kw}' in '{loc}' (need {remaining} more)...")
                                    
                                    try:
                                        results = applier.live_apply_xing(
                                            keyword=kw,
                                            location=loc,
                                            target_count=remaining
                                        )
                                        
                                        total_applied += len(results.get("applied", []))
                                        total_skipped += len(results.get("skipped", []))
                                        total_errors += len(results.get("errors", []))
                                        st.session_state['applied_jobs'] = db.load_applied()
                                        
                                    except Exception as e:
                                        st.error(f"Xing error: {e}")
                    
                    applier.close()
                    status_box.success(f"🎉 Live Apply Complete! Applied: {total_applied} | Skipped: {total_skipped} | Errors: {total_errors}")
                
                else:
                    # STANDARD SCRAPE MODE
                    from job_hunter.scout import Scout
                    scout = Scout()
                    platforms_arg = selected_platforms if selected_platforms else ["LinkedIn"]
                    
                    total = len(st.session_state['resumes'])
                    
                    for idx, (role_name, role_data) in enumerate(st.session_state['resumes'].items()):
                        raw_kw = role_data.get("target_keywords", "")
                        keywords = [k.strip() for k in raw_kw.split(';') if k.strip()]
                        if not keywords: keywords = [role_name]
                        
                        locations = [l.strip() for l in scrape_location.split(';') if l.strip()]
                        if not locations: locations = ["Germany"]

                        for kw in keywords:
                            for loc in locations:
                                status_box.info(f"🚀 [{idx+1}/{total}] Scouting for **{kw}** in **{loc}** ({role_name})...")
                                
                                try:
                                    scout.launch_mission(
                                         keyword=kw, 
                                         location=loc, 
                                         limit=scrape_limit, 
                                         platforms=platforms_arg,
                                         easy_apply=False
                                    )
                                except Exception as e: 
                                    st.error(f"Failed for {kw} in {loc}: {e}")
                    
                    status_box.success("🎉 All Missions Complete! Taking you to results...")
                
                st.cache_data.clear() # Clear cache to load new data
                st.session_state['page'] = 'explorer'
                time.sleep(1) # Visual pause
                st.rerun()

# ... (later in file)

    with col_skip:
         if st.button("📂 Load Existing Jobs (Skip Scrape)", width="stretch"):
             st.cache_data.clear() # Refresh in case file changed externally
             st.session_state['page'] = 'explorer'
             st.rerun()

# ==========================================
# VIEW 2: MISSION CONTROL (EXPLORER)
# ==========================================

# ==========================================
# VIEW 2: MISSION CONTROL (EXPLORER)
# ==========================================
elif st.session_state['page'] == 'explorer':
    
    # Header
    st.title("🔎 Mission Results")

    df = load_data()
    
    if df.empty:
        st.warning("No data found. Please go back and run a search.")
    else:

        # --- BLACKLIST MANAGER ---
        with st.expander("🚫 Blacklist Manager (Quick Block)", expanded=False):
             bl_data = db.load_blacklist()
             bl_companies_str = "; ".join(bl_data.get("companies", []))
             bl_titles_str = "; ".join(bl_data.get("titles", []))
             bl_safe_str = "; ".join(bl_data.get("safe_phrases", []))
             
             st.caption(f"Add companies or titles here to drop them. SAFE PHRASES will rescue a job if it contains a blacklisted title word.\n\nUse ';' to separate multiple entries.")
             
             c_bl1, c_bl2, c_bl3 = st.columns(3)
             new_companies = c_bl1.text_area("Block Companies", value=bl_companies_str, help="e.g. BadCorp; Boring Ltd", key="bl_comp_mgr")
             new_titles = c_bl2.text_area("Block Job Titles", value=bl_titles_str, help="e.g. Intern; Unpaid", key="bl_title_mgr")
             new_safe = c_bl3.text_area("Safe Phrases (Rescue)", value=bl_safe_str, help="e.g. Analyst; Manager", key="bl_safe_mgr")
             
             if c_bl1.button("Save Updates", key="btn_save_bl"):
                 c_list = [c.strip() for c in new_companies.split(';') if c.strip()]
                 t_list = [t.strip() for t in new_titles.split(';') if t.strip()]
                 s_list = [s.strip() for s in new_safe.split(';') if s.strip()]
                 db.save_blacklist(c_list, t_list, s_list)
                 st.toast("Blacklist Updated! 🛡️")


        # Pre-calculate filtered for logic (no filters really, just load)
        filtered = df.copy()
        def get_status(row):
            jid = f"{row['Job Title']}-{row['Company']}"
            if jid in st.session_state['applied_jobs']: return "✅ Applied"
            return ""
        filtered["Status"] = filtered.apply(get_status, axis=1)

        # --- SNAPSHOT STRATEGY ---
        if 'applied_snapshot' not in st.session_state:
             st.session_state['applied_snapshot'] = set(st.session_state['applied_jobs'].keys())
             
        # ----------------------------------------------------
        # A. JOB APPLICATION CENTER
        # ----------------------------------------------------
        with st.expander("🏭 Job Application Center", expanded=True):
             
             # a1. Fetch Complete Details Button
             # --- FETCH DETAILS BUTTON ---
            if st.button("🕵️ Fetch Complete Details (Deep Scrape)", help="Visits every link to get full JD, Date, and Location. This takes time!"):
                 from job_hunter.content_fetcher import ContentFetcher
                 fetcher = ContentFetcher()
                 
                 prog_bar = st.progress(0)
                 status_txt = st.empty()
                 
                 jobs_to_process = filtered.to_dict('records')
                 total_fetch = len(jobs_to_process)
                 
                 updated_count = 0
                 
                 for i, job_row in enumerate(jobs_to_process):
                    # CHECK: Do we need to process this?
                    has_desc = job_row.get("Rich Description") and len(str(job_row.get("Rich Description"))) > 100
                    has_lang = job_row.get("Language") and job_row.get("Language") not in ["Unknown", "None", None]
                    
                    # 1. OPTIMIZED SKIP: If we have both, truly skip
                    if has_desc and has_lang:
                        prog_bar.progress((i + 1) / total_fetch)
                        continue

                    # 2. BACKFILL: If we have desc but no lang, just detect locally!
                    if has_desc and not has_lang:
                        status_txt.text(f"Detecting Language {i+1}/{total_fetch}: {job_row.get('Job Title')}")
                        try:
                           from langdetect import detect
                           txt = str(job_row.get("Rich Description"))
                           detected_lang = detect(txt) if len(txt) > 50 else "en"
                           
                           # SAVE
                           target_link = job_row.get("Web Address") or job_row.get("link")
                           scouted_data = db.load_scouted()
                           for s_job in scouted_data:
                               if s_job.get('link') == target_link:
                                   s_job['language'] = detected_lang
                                   break
                           db.save_scouted_jobs(scouted_data, append=False)
                           updated_count += 1
                        except: pass
                        prog_bar.progress((i + 1) / total_fetch)
                        continue

                    # 3. FULL FETCH: Missing Desc (and likely Lang)
                    status_txt.text(f"Fetching {i+1}/{total_fetch}: {job_row.get('Job Title')}")
                    
                    url = job_row.get("Web Address") or job_row.get("link")
                    platform = job_row.get("Platform") or job_row.get("platform")
                    
                    details = fetcher.fetch_details(url, platform)
                    if details:
                        # Match by LINK
                        target_link = job_row.get("Web Address") or job_row.get("link")
                        scouted_data = db.load_scouted()
                        for s_job in scouted_data:
                            if s_job.get('link') == target_link:
                                s_job['rich_description'] = details.get('description', '')
                                s_job['language'] = details.get('language', 'Unknown')
                                new_company = details.get('company')
                                if new_company and new_company != s_job.get('company'):
                                    if "earn up to" not in new_company.lower():
                                        s_job['company'] = new_company
                                break
                        db.save_scouted_jobs(scouted_data, append=False)
                        updated_count += 1
                    
                    prog_bar.progress((i + 1) / total_fetch)
                 
                 fetcher.close()
                 st.toast(f"Updated {updated_count} jobs with deep details!")
                 st.cache_data.clear()
                 st.rerun()

            # a2. Job Scraped Grid
            st.caption("Select a job to Analysis.")

            # --- SORT & FREEZE LOGIC ---
            if 'frozen_order' not in st.session_state:
                st.session_state['frozen_order'] = None

            # Logic to sort 'filtered' BEFORE display_df creation
            
            # If Frozen, enforce order
            if st.session_state['frozen_order']:
                # Filter 'filtered' to match frozen order and sort by it
                ordered_ids = st.session_state['frozen_order']
                
                # Create a mapping for sorting
                # We need to reconstruct the dataframe in the specific order of IDs
                filtered['temp_sort_key'] = filtered.apply(lambda x: f"{x['Job Title']}-{x['Company']}", axis=1)
                
                # Filter out any that might have been deleted, keep only those in frozen list? 
                # Or just prioritize them. Let's keep strict for now.
                # Actually, if we just set index to the ID, we can reindex.
                filtered.set_index('temp_sort_key', inplace=True)
                
                # Reindex with the frozen list (intersection to be safe)
                valid_ids = [i for i in ordered_ids if i in filtered.index]
                filtered = filtered.loc[valid_ids].reset_index() # temp_sort_key becomes column
                
                # Add Index Column
                filtered.insert(0, "Index", range(1, len(filtered) + 1))
                
                # Display Status
                c_frz1, c_frz2 = st.columns([3, 1])
                c_frz1.info(f"❄️ Sort Frozen ({len(filtered)} jobs). Index active.")
                if c_frz2.button("🔓 Unfreeze", width="stretch"):
                    st.session_state['frozen_order'] = None
                    st.rerun()
                    
            else:
                # Normal State: Show Sort Controls
                c_sort1, c_sort2 = st.columns([3, 1])
                sort_col = c_sort1.selectbox("Sort by:", ["Default (Scraped Order)", "Company", "Target Role (Found_job)", "Platform", "Job Title"])
                
                # Apply Sort
                if sort_col == "Company":
                    filtered = filtered.sort_values("Company", key=lambda col: col.str.lower())
                elif sort_col == "Target Role (Found_job)":
                    filtered = filtered.sort_values("Found_job", key=lambda col: col.str.lower())
                elif sort_col == "Platform":
                     filtered = filtered.sort_values("Platform")
                elif sort_col == "Job Title":
                     filtered = filtered.sort_values("Job Title", key=lambda col: col.str.lower())
                
                # Freeze Button
                if c_sort2.button("❄️ Freeze Sort", help="Locks the current order and adds an Index number.", width="stretch"):
                    # Capture IDs in current order
                    current_ids = filtered.apply(lambda x: f"{x['Job Title']}-{x['Company']}", axis=1).tolist()
                    st.session_state['frozen_order'] = current_ids
                    st.rerun()

            
            # Create display DF
            display_cols = [c for c in filtered.columns if c != "Rich Description" and c != "temp_sort_key"]
            display_df = filtered[display_cols].copy()
            
            def is_applied_snapshot(row):
                jid = f"{row['Job Title']}-{row['Company']}"
                return jid in st.session_state['applied_snapshot']
                
            if "selected_job_id" not in st.session_state: st.session_state["selected_job_id"] = None
            
            # Add Select Column
            def is_selected(row):
                jid = f"{row['Job Title']}-{row['Company']}"
                return jid == st.session_state["selected_job_id"]
                
            display_df.insert(0, "Select", display_df.apply(is_selected, axis=1).astype(bool))
            display_df.insert(1, "Applied", display_df.apply(is_applied_snapshot, axis=1).astype(bool))
            display_df.insert(2, "Delete", False)
            display_df["Delete"] = display_df["Delete"].astype(bool)
            display_df.insert(3, "Park", False)
            display_df["Park"] = display_df["Park"].astype(bool)
            
            # FILTER SECTION
            with st.expander("🔍 Filter Jobs", expanded=False):
                c_col, c_search, c_clear = st.columns([2, 3, 1])
                
                # Get filterable columns
                filterable_cols = [c for c in display_df.columns if c not in ["Select", "Applied", "Delete", "Park"]]
                
                filter_col = c_col.selectbox("Column", filterable_cols, key="filter_column")
                filter_term = c_search.text_input("Contains", placeholder="Type to filter...", key="filter_term")
                
                if c_clear.button("🔄 Clear", use_container_width=True):
                    st.session_state["filter_term"] = ""
                    st.rerun()
                
                # Apply filter
                if filter_term:
                    display_df = display_df[display_df[filter_col].astype(str).str.contains(filter_term, case=False, na=False)]
                    st.caption(f"Showing {len(display_df)} jobs matching '{filter_term}' in '{filter_col}'")
            
            # Toggle Filter
            c_tog, _ = st.columns([1, 4])
            hide_applied = c_tog.toggle("Hide Applied Jobs", value=False)
            
            if hide_applied:
                display_df = display_df[~display_df["Applied"]]

            # Config Map
            cfg = {
                    "Select": st.column_config.CheckboxColumn("Select", width="small"),
                    "Applied": st.column_config.CheckboxColumn("Applied", help="Check to mark as applied", width="small"),
                    "Delete": st.column_config.CheckboxColumn("Delete", help="Check to delete this job permanently", width="small"),
                    "Park": st.column_config.CheckboxColumn("Park", help="Park this job (hide and ignore)", width="small"),
                    "Web Address": st.column_config.LinkColumn("Apply", display_text="Link"),
                    "Job Title": st.column_config.TextColumn("Title", width="large"),
                    "Company": st.column_config.TextColumn("Company", width="medium"),
                    "Platform": st.column_config.TextColumn("Source", width="small"),
                    "Found_job": st.column_config.TextColumn("Target Role", width="medium"), 
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "description": st.column_config.TextColumn("Original Desc", width="small"), 
                    "language": st.column_config.TextColumn("Language", width="small"),
                }
            
            if "Index" in display_df.columns:
                cfg["Index"] = st.column_config.NumberColumn("#", width="small", format="%d")

            edited_df = st.data_editor(
                display_df,
                column_config=cfg,
                disabled=[c for c in display_df.columns if c not in ["Applied", "Select", "Delete", "Park"]], 
                # use_container_width=True, # DEPRECATED
                width="stretch", 
                hide_index=True, 
                on_change=None, 
                key="job_editor" 
            )

            # a3. End Day / Archive Applied
            st.markdown("###")
            
            c_end, c_easy = st.columns(2)
            
            with c_end:
                if st.button("🏁 End Day / Archive Applied", help="Removes all Applied jobs from the active 'Scouted' list.", use_container_width=True):
                     archived_count = db.archive_applied_jobs()
                     if archived_count > 0:
                         st.toast(f"Archived {archived_count} jobs from current view!", icon="🧹")
                         st.cache_data.clear()
                         st.rerun()
                     else:
                         st.toast("No new applied jobs to archive.", icon="ℹ️")
            
            with c_easy:
                # Count eligible jobs
                apply_platforms = ["LinkedIn", "Xing"]
                eligible_for_easy = display_df[display_df["Platform"].isin(apply_platforms)]
                eligible_count = len(eligible_for_easy)
                
                if st.button(f"🤖 Easy Apply All ({eligible_count} jobs)", type="primary", use_container_width=True, disabled=(eligible_count == 0)):
                    st.session_state['show_easy_apply_confirm'] = True
            
            # CONFIRMATION DIALOG
            if st.session_state.get('show_easy_apply_confirm', False):
                st.warning("⚠️ **Confirmation Required**")
                st.markdown(f"""
                **Are you sure you want to start Easy Apply?**
                
                The bot will:
                1. Open **{eligible_count}** LinkedIn/Xing jobs one by one
                2. Check if each job has "Easy Apply" option
                3. If yes → Apply automatically using your resume
                4. If no → Skip to next job
                
                ⏱️ This may take **{eligible_count * 10 // 60} - {eligible_count * 15 // 60} minutes**
                """)
                
                # Resume Selection
                resume_options = list(st.session_state.get('resumes', {}).keys())
                if resume_options:
                    easy_resume_key = st.selectbox("Select Resume", resume_options, key="easy_apply_confirm_resume")
                    easy_resume_path = st.session_state['resumes'].get(easy_resume_key, {}).get('file_path', '')
                else:
                    st.error("❌ No resume uploaded! Go to Home page to add one.")
                    easy_resume_path = ''
                
                easy_phone = st.text_input("Phone Number (optional)", key="easy_apply_confirm_phone", placeholder="+49 123 456789")
                
                c_yes, c_no = st.columns(2)
                
                if c_yes.button("✅ Confirm Auto-Apply", type="primary", use_container_width=True, disabled=not easy_resume_path):
                    st.session_state['show_easy_apply_confirm'] = False
                    st.session_state['easy_apply_running'] = True
                    
                    # START THE MAZDOORI!
                    from job_hunter.applier import JobApplier
                    
                    applier = JobApplier(resume_path=easy_resume_path, phone_number=easy_phone)
                    
                    prog = st.progress(0)
                    status = st.empty()
                    results_log = []
                    
                    jobs_list = eligible_for_easy.to_dict('records')
                    total = len(jobs_list)
                    
                    applied_count = 0
                    skipped_count = 0
                    
                    for i, job in enumerate(jobs_list):
                        job_url = job.get("Web Address") or job.get("link")
                        platform = job.get("Platform") or job.get("platform")
                        title = job.get("Job Title") or job.get("title")
                        company = job.get("Company") or job.get("company")
                        
                        status.text(f"🔍 Checking {i+1}/{total}: {title} @ {company}")
                        
                        success, message, is_easy = applier.apply(job_url, platform, job_title=title, company=company)
                        
                        if not is_easy:
                            skipped_count += 1
                            results_log.append({"Job": title, "Company": company, "Status": "⏭️ Skipped", "Message": "Not Easy Apply"})
                        elif success:
                            applied_count += 1
                            results_log.append({"Job": title, "Company": company, "Status": "✅ Applied", "Message": message})
                            jid = f"{title}-{company}"
                            job_data = {"Job Title": title, "Company": company, "Web Address": job_url, "Platform": platform}
                            st.session_state['applied_jobs'] = db.save_applied(jid, job_data, {"auto_applied": True})
                        else:
                            results_log.append({"Job": title, "Company": company, "Status": "❌ Failed", "Message": message})
                        
                        prog.progress((i + 1) / total)
                    
                    applier.close()
                    st.session_state['easy_apply_running'] = False
                    
                    # RESULTS
                    st.success(f"🎉 **Mazdoori Complete!** Applied: {applied_count} | Skipped: {skipped_count} | Failed: {total - applied_count - skipped_count}")
                    
                    with st.expander("📝 Full Log", expanded=True):
                        for r in results_log:
                            st.write(f"{r['Status']} **{r['Job']}** @ {r['Company']}: {r['Message']}")
                    
                    st.cache_data.clear()
                    st.rerun()
                
                if c_no.button("❌ Cancel", use_container_width=True):
                    st.session_state['show_easy_apply_confirm'] = False
                    st.rerun()


            # a4. BULK ACTIONS (LANGUAGE)
            with st.expander("⚡ Bulk Actions (Language)", expanded=False):
                st.caption("Perform actions on ALL jobs matching a specific language.")
                
                # Get available languages from filtered view
                if "Language" in filtered.columns:
                     langs = filtered["Language"].astype(str).unique().tolist()
                else: langs = []
                
                if langs:
                    c_b_sel, c_b_btn1, c_b_btn2 = st.columns([2, 1, 1])
                    selected_bulk_lang = c_b_sel.selectbox("Select Language", langs, key="bulk_lang_sel")
                    
                    # Count impacted
                    count_impact = len(filtered[filtered["Language"].astype(str) == selected_bulk_lang])
                    c_b_sel.caption(f"Impacts {count_impact} jobs.")
                    
                    if c_b_btn1.button(f"🗑️ Delete All '{selected_bulk_lang}'", use_container_width=True, type="primary"):
                         # Execute Delete
                         jobs_to_del = filtered[filtered["Language"].astype(str) == selected_bulk_lang].to_dict('records')
                         for j in jobs_to_del:
                             db.delete_scouted_job(j.get('Job Title'), j.get('Company'))
                         
                         st.toast(f"Deleted {len(jobs_to_del)} jobs!", icon="🗑️")
                         st.cache_data.clear()
                         st.rerun()

                    if c_b_btn2.button(f"🅿️ Park All '{selected_bulk_lang}'", use_container_width=True):
                         # Execute Park
                         jobs_to_park = filtered[filtered["Language"].astype(str) == selected_bulk_lang].to_dict('records')
                         for j in jobs_to_park:
                             # Reconstruct full row dict for parking logic if needed
                             # But db.park_job expects minimal or we give it what we have
                             # The UI columns might be renamed, we need to map back if park_job relies on 'link' vs 'Web Address'
                             # Fortunately park_job handles flexible keys or we pass the dict
                             # Let's ensure keys match what park_job expects (it checks 'link'/'platform' inside)
                             db.park_job(j.get('Job Title'), j.get('Company'), j)
                             
                         st.toast(f"Parked {len(jobs_to_park)} jobs!", icon="🅿️")
                         st.cache_data.clear()
                         st.rerun()
                else:
                    st.info("No language data available to filter.")
            

            # Change Detection Logic (Inside Expander or just before Analysis)
            # We keep it here to run before Analysis panel rendering updates
            changes_detected = False
            
            if not edited_df.empty:
                # Optimization: compare with st.session_state['applied_jobs'] directly
                for idx, row in edited_df.iterrows():
                    jid = f"{row['Job Title']}-{row['Company']}"
                    
                    # 1. HANDLE SELECTION
                    user_selected = row['Select']
                    is_currently_selected = (jid == st.session_state["selected_job_id"])
                    
                    if user_selected and not is_currently_selected:
                        st.session_state["selected_job_id"] = jid
                        changes_detected = True
                        break 
                    elif not user_selected and is_currently_selected:
                        st.session_state["selected_job_id"] = None
                        changes_detected = True

                    # 2. HANDLE DELETE
                    if row.get('Delete', False):
                        st.session_state['pending_delete_job'] = {
                            "title": row['Job Title'],
                            "company": row['Company']
                        }
                        changes_detected = True
                        break

                    # 3. HANDLE PARK
                    if row.get('Park', False):
                         # Store pending action instead of acting immediately
                         st.session_state['pending_park_job'] = {
                             "title": row['Job Title'],
                             "company": row['Company'],
                             "full_row": row.to_dict() # FIX: Convert to dict to avoid checking Series truth value
                         }
                         changes_detected = True
                         break

                    # 4. HANDLE APPLIED
                    user_wants_applied = row['Applied']
                    db_is_applied = jid in st.session_state['applied_jobs']
                    
                    if user_wants_applied and not db_is_applied:
                         current_analysis = st.session_state['job_cache'].get(jid, {})
                         original_row = filtered.loc[idx]
                         mark_as_applied(jid, original_row, current_analysis)
                         st.session_state['applied_snapshot'].add(jid)
                         changes_detected = True
                         
                    elif not user_wants_applied and db_is_applied:
                         del st.session_state['applied_jobs'][jid]
                         db.delete_applied(jid)
                         if jid in st.session_state['applied_snapshot']:
                            st.session_state['applied_snapshot'].remove(jid)
                         st.toast(f"Removed '{row['Job Title']}' from history.", icon="🗑️")
                         changes_detected = True

            # Delete Confirmation (Inside Expander)
            if st.session_state.get('pending_delete_job'):
                job_to_delete = st.session_state['pending_delete_job']
                with st.container(border=True):
                    st.error(f"⚠️ Are you sure you want to delete '{job_to_delete['title']}' at '{job_to_delete['company']}'?")
                    col_confirm, col_cancel = st.columns(2)
                    if col_confirm.button("✅ Yes, Delete Forever", type="primary"):
                        db.delete_scouted_job(job_to_delete['title'], job_to_delete['company'])
                        st.session_state['pending_delete_job'] = None
                        st.cache_data.clear()
                        st.rerun()
                    if col_cancel.button("❌ Cancel"):
                        st.session_state['pending_delete_job'] = None
                        st.rerun()

            # Park Confirmation
            if st.session_state.get('pending_park_job'):
                job_to_park = st.session_state['pending_park_job']
                with st.container(border=True):
                    st.info(f"🅿️ Park '{job_to_park['title']}' at '{job_to_park['company']}'? (Will be hidden and ignored)")
                    c_pk1, c_pk2 = st.columns(2)
                    if c_pk1.button("✅ Yes, Park It", type="primary"):
                        db.park_job(job_to_park['title'], job_to_park['company'], job_to_park['full_row'])
                        st.session_state['pending_park_job'] = None
                        st.toast(f"Parked '{job_to_park['title']}'")
                        st.cache_data.clear()
                        st.rerun()
                    if c_pk2.button("❌ Cancel", key="cancel_park"):
                        st.session_state['pending_park_job'] = None
                        st.rerun()

            # if changes_detected:
            #    st.rerun()

            # Selection Logic (Resolve Index)
            current_selection = None
            if st.session_state["selected_job_id"]:
                 try:
                     for idx, row in filtered.iterrows():
                         jid = f"{row['Job Title']}-{row['Company']}"
                         if jid == st.session_state["selected_job_id"]:
                             current_selection = filtered.index.get_loc(idx)
                             break
                 except Exception as e:
                     st.session_state["selected_job_id"] = None
            
            # Analysis Panel (MOVED INSIDE EXPANDER)
            if current_selection is not None:
                idx = current_selection
                job = filtered.iloc[idx]
                job_id = f"{job['Job Title']}-{job['Company']}"
                
                st.divider() # Separation line as requested
                st.header(f"🤖 Analysis: {job['Job Title']}")
                
                # ... (Keep Analysis Logic same, just indented)
                search_keyword = job.get('Found_job', '')
                available_resumes = list(st.session_state['resumes'].keys())
                selected_resume_key = available_resumes[0] if available_resumes else None
                if search_keyword in st.session_state['resumes']:
                    selected_resume_key = search_keyword
                else:
                     for rk in available_resumes:
                         if rk.lower() in search_keyword.lower() or search_keyword.lower() in rk.lower():
                             selected_resume_key = rk
                             break
                
                if not available_resumes:
                    st.error("❌ No active resumes found.")
                    selected_resume_data = {"text": "", "bytes": None}
                else:
                    col_sel_res, col_sel_comp = st.columns([2, 2])
                    selected_resume_key = col_sel_res.selectbox("Using Persona:", available_resumes, index=available_resumes.index(selected_resume_key) if selected_resume_key in available_resumes else 0)
                    selected_resume_data = st.session_state['resumes'][selected_resume_key]

                    analysis_options = {
                        "Cover Letter": "cover_letter",
                        "Company Intel": "intel",
                        "ATS Match": "ats",
                        "Strategized Resume": "resume"
                    }
                    selected_components = col_sel_comp.multiselect(
                        "Analyze Components:",
                        options=list(analysis_options.keys()),
                        default=["Cover Letter"],
                        help="Select which AI analysis components to run. Fewer components save API quota."
                    )

                # Action Bar
                c_act1, c_act2, c_act3 = st.columns([2, 2, 2])
                is_cached = (job_id in st.session_state['job_cache'])
                is_applied = (job_id in st.session_state['applied_jobs'])
                
                if is_cached and st.session_state.get('analyzed_job_id') != job_id:
                    st.session_state['analysis_results'] = st.session_state['job_cache'][job_id]
                    st.session_state['analyzed_job_id'] = job_id

                with c_act1:
                     if is_applied: st.success("✅ Applied")
                     else: st.write("")

                with c_act2:
                    if not is_applied:
                        if st.button("📝 Mark as Applied", width="stretch"):
                            current_analysis = st.session_state['analysis_results'] if job_id in st.session_state['job_cache'] else {}
                            mark_as_applied(job_id, job, current_analysis)
                            st.rerun()

                with c_act3:
                    has_resume = len(selected_resume_data.get('text', '')) > 0
                    has_details = bool(job.get('Rich Description') and str(job.get('Rich Description')) != 'nan' and len(str(job.get('Rich Description'))) > 50)
                    can_run = has_resume and has_details
                    btn_text = "🔄 Re-Analyze" if is_cached else "✨ Run AI Analysis"
                    
                    if st.button(btn_text, type="primary" if not is_cached else "secondary", disabled=not can_run or not selected_components, width="stretch"):
                         with st.spinner(f"Analyzing for '{selected_resume_key}'..."):
                            scraped_jd = job.get('Job Description', '')
                            if job.get('Rich Description'): scraped_jd = job.get('Rich Description')

                            if scraped_jd and len(scraped_jd) > 50 and scraped_jd != "N/A":
                                context = f"Title: {job['Job Title']}\nCompany: {job['Company']}\nLoc: {job['Location']}\nLink: {job.get('Web Address','')}\n\nJOB DESCRIPTION:\n{scraped_jd}"
                            else:
                                context = f"Title: {job['Job Title']}\nCompany: {job['Company']}\nLoc: {job['Location']}\nLink: {job.get('Web Address','')}"
                                context += "\n(Text unavailable.)"
                            try:
                                crew = JobAnalysisCrew(context, selected_resume_data['text'])
                                comp_keys = [analysis_options[c] for c in selected_components]
                                results = crew.run_analysis(components=comp_keys)

                                # Merge with existing cache if any
                                if job_id in st.session_state['job_cache']:
                                    new_results = st.session_state['job_cache'][job_id].copy()
                                    new_results.update(results)
                                    results = new_results

                                st.session_state['job_cache'][job_id] = results
                                st.session_state['job_cache'] = db.save_cache(job_id, results)
                                if is_applied:
                                     current_record = st.session_state['applied_jobs'][job_id]
                                     st.session_state['applied_jobs'] = db.save_applied(job_id, current_record.get('job_details', {}), results, current_record.get('status', 'applied'))
                                     st.toast("Updated History! ♻️")
                                st.session_state['analysis_results'] = results
                                st.session_state['analyzed_job_id'] = job_id
                                st.rerun()
                            except Exception as e: st.error(f"Error: {e}")
                
                if not has_resume: st.warning("⚠️ Resume empty.")
                if not has_details: st.warning("⚠️ Please 'Fetch Complete Details' first.")
                
                # Display Results
                # Display Results or Placeholders
                # We always show tabs, but content depends on analysis state
                
                # Check if this specific job has analysis results in session state
                is_analyzed = (st.session_state.get('analyzed_job_id') == job_id)
                analysis_results = st.session_state['analysis_results'] if is_analyzed else {}

                tab1, tab2, tab3, tab4, tab5 = st.tabs(["💡 Intel", "📝 Cover Letter", "🎯 ATS Match", "📄 Strategized Resume", "💬 Ask AI"])
                
                with tab1:
                    if not is_analyzed:
                        st.info("ℹ️ Run AI Analysis to see Deep Intel.")
                    else:
                        intel = analysis_results.get("intel", {}) or analysis_results.get("company_intel", {})
                        st.subheader("🏢 Deep Intel")
                        st.write(f"**Mission**: {intel.get('mission', 'N/A')}")
                        st.markdown("---")
                        xi1, xi2 = st.columns(2)
                        xi1.metric("HQ", intel.get("headquarters", "N/A"))
                        xi2.metric("Size", intel.get("employees", "N/A"))
                        st.metric("Branches", intel.get("branches", "N/A"))
                        st.markdown("**Key Facts**:")
                        for f in intel.get('key_facts', []): st.markdown(f"• {f}")

                with tab2:
                    if not is_analyzed:
                        st.info("ℹ️ Run AI Analysis to generate a Cover Letter.")
                    else:
                        st.subheader("📝 AI Cover Letter")

                        # Humanization Score
                        h_score = analysis_results.get("humanization_score", 0)
                        if h_score > 0:
                            st.write(f"**Humanization Level:** {h_score}%")
                            st.progress(h_score / 100)
                            if h_score > 90:
                                st.success("✅ This letter is highly humanized and likely to bypass AI detectors.")
                            elif h_score > 70:
                                st.info("ℹ️ This letter has good humanization but could be improved further.")
                            else:
                                st.warning("⚠️ Humanization score is low. Consider manual editing.")

                        cover_letter = analysis_results.get("cover_letter", "No cover letter generated yet.")
                        st.text_area("Cover Letter", cover_letter, height=500)
                    
                with tab3:
                    if not is_analyzed:
                         st.info("ℹ️ Run AI Analysis to see ATS Match Score.")
                    else:
                        ats = analysis_results.get("ats", {}) or analysis_results.get("ats_report", {})
                        sc = ats.get('score', 0)
                        st.subheader("🎯 ATS Match")
                        st.metric("Score", f"{sc}%")
                        st.progress(sc/100)
                        st.write("**You are missing:**")
                        for k in ats.get("missing_skills", []): st.caption(f"❌ {k}")

                with tab4:
                    if not is_analyzed:
                         st.info("ℹ️ Run Analysis to see Strategized Resume.")
                    else:
                        st.subheader("📄 Strategized Resume (Experience)")
                        strat_resume = analysis_results.get("tailored_resume", "No tailored resume generated.")
                        st.text_area("Tailored Experience", strat_resume, height=500)

                with tab5:
                    st.header("Ask the AI Interview Guide")
                    st.caption(f"Context: {selected_resume_key}")
                    col_jd, col_res = st.columns(2)
                    with col_jd:
                        st.subheader("📋 Job Description")
                        jd_text = job.get('Rich Description') or job.get('rich_description') or job.get('Job Description') or job.get('description') or 'No JD available.'
                        st.text_area("JD Content", jd_text, height=500, label_visibility="collapsed")
                    with col_res:
                        st.subheader("📄 Your Resume")
                        if selected_resume_data.get('bytes'):
                            b64_pdf = base64.b64encode(selected_resume_data['bytes']).decode('utf-8')
                            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
                            st.markdown(pdf_display, unsafe_allow_html=True)
                        else:
                            st.text_area("Resume Content", selected_resume_data.get('text', ''), height=450)

                    st.divider()
                    st.subheader("💬 Interview Chat")
                    if "chat_history" not in st.session_state: st.session_state.chat_history = {}
                    
                    # Initialize chat history for this job if not exists
                    if job_id not in st.session_state.chat_history:
                        # Try to load legacy QnA if available, else empty
                        st.session_state.chat_history[job_id] = analysis_results.get("qna_history", [])

                    for msg in st.session_state.chat_history[job_id]:
                        with st.chat_message(msg["role"]): st.write(msg["content"])
                    
                    chat_placeholder = "Ask about this job..."

                    if user_query := st.chat_input(chat_placeholder, key=f"chat_{job_id}"):
                        st.session_state.chat_history[job_id].append({"role": "user", "content": user_query})
                        with st.chat_message("user"): st.write(user_query)
                        with st.chat_message("assistant"):
                            with st.spinner("Thinking..."):
                                from job_hunter.model_factory import get_llm
                                llm = get_llm()
                                jd = job.get('Rich Description') or job.get('rich_description') or job.get('Job Description') or job.get('description') or 'No JD available.'
                                context = f"Job: {job.get('Job Title', '')} at {job.get('Company', '')}\nJD: {jd}\nResume: {selected_resume_data.get('text', '')}"
                                prompt = f"Context:\n{context}\n\nUser Question: {user_query}\n\nROLE: Interview Prep Guide.\nSTRICT: Only answer job/resume related questions.\nAnswer:"
                                response = llm.invoke(prompt).content
                                st.write(response)
                            st.session_state.chat_history[job_id].append({"role": "assistant", "content": response})
                            
                            # Only update cache/results if we actually have a valid analysis_results object to write to
                            # If is_analyzed is False, we might just be chatting ephemerally or we can init an empty result object
                            if is_analyzed:
                                st.session_state['analysis_results']['qna_history'] = st.session_state.chat_history[job_id]
                                st.session_state['job_cache'][job_id] = st.session_state['analysis_results']
                                db.save_cache(job_id, st.session_state['analysis_results'])
                            else:
                                # Save chat history even if no full analysis exists yet
                                # logic needed: create a dummy result object? or just rely on session_state.chat_history?
                                # For now, let's try to save it to cache so it persists
                                 if job_id not in st.session_state['job_cache']:
                                     st.session_state['job_cache'][job_id] = {}
                                 st.session_state['job_cache'][job_id]['qna_history'] = st.session_state.chat_history[job_id]
                                 db.save_cache(job_id, st.session_state['job_cache'][job_id])

                            if is_applied:
                                 current = st.session_state['applied_jobs'][job_id]
                                 # Ensure we have a valid object to save
                                 payload = st.session_state['job_cache'][job_id]
                                 db.save_applied(job_id, current['job_details'], payload, current['status'])
                                 st.toast("Chat saved!", icon="💾")
                                 st.rerun()
                            
                            st.rerun()
        # ----------------------------------------------------
        # B. METRICS AND VISUALISATIONS (MOVED TO BOTTOM)
        # ----------------------------------------------------
        st.markdown("---") # Global separator
        with st.expander("📈 Metrics and Visualisations", expanded=False):
            render_metrics_dashboard(df, st.session_state['applied_jobs'], len(db.load_parked()))


# ==========================================
# VIEW 4: NETWORKING (LINKEDIN OUTREACH)
# ==========================================
elif st.session_state['page'] == 'networking':
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

# ==========================================
# VIEW 3: APPLIED JOBS (HISTORY)
# ==========================================
elif st.session_state['page'] == 'applied':
    # Sidebar handled globally

    
    st.title("📂 Applied Jobs History")
    
    # --- RENDER DASHBOARD ---
    # For Applied View, "Current" is implicit if we load it, or we just pass empty if we want to isolate?
    # User wanted "Same with Breakdown", so we should ideally show global stats.
    # Let's load current scouted for stats
    current_scouted_data = db.load_scouted() # Raw list
    if current_scouted_data:
        current_df_stats = pd.DataFrame(current_scouted_data)
    else:
        current_df_stats = pd.DataFrame(columns=["Platform"])
        
    render_metrics_dashboard(current_df_stats, st.session_state['applied_jobs'], len(db.load_parked()))

    # --- GRAND MASTER STRATEGIST (CAREER AUDIT) ---
    st.markdown("---")
    with st.expander("♟️ Career Strategy Audit (Grand Master)", expanded=False):
        st.write("Analyze your applied jobs collectively to find out why you are not getting interviews.")
        
        # Resume Text (Hidden or Loaded from Config/Session)
        resume_text_audit = ""
        # Try to find a resume in session or config
        try:
             with open("data/resume_config.json", "r", encoding="utf-8") as rf:
                 rdata = json.load(rf)
                 resume_text_audit = rdata.get("text", "")
        except: pass
        
        ca_col1, ca_col2 = st.columns([1, 3])
        
        with ca_col1:
            st.write("") # Spacer to align with uploader
            st.write("") 
            run_audit = st.button("🚀 Run Audit", type="primary", use_container_width=True)
            
        with ca_col2:
            uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"], key="audit_resume_up", label_visibility="visible")

        # Handle Upload
        if uploaded_file:
             from job_hunter.resume_parser import parse_resume
             text = parse_resume(uploaded_file)
             if text and len(text) > 50:
                 # Save to config
                 with open("data/resume_config.json", "w", encoding="utf-8") as f:
                     json.dump({"filename": uploaded_file.name, "text": text}, f)
                 resume_text_audit = text
                 st.toast("Resume Updated!", icon="✅")
             else:
                 st.error("Could not parse resume text.")

        if run_audit:
             if not resume_text_audit:
                 st.error("No resume found! Please upload your resume using the button above.")
             else:
                 with st.spinner("Analyzing 250+ Jobs... This may take a minute..."):
                     from job_hunter.career_auditor import CareerAuditor
                     auditor = CareerAuditor()
                     audit_result = auditor.run_audit(resume_text_audit)
                     st.session_state['last_audit_result'] = audit_result
                     db.save_audit_report(audit_result)
                     st.toast("Audit Complete & Saved!", icon="💾")
        
        if 'last_audit_result' in st.session_state and st.session_state['last_audit_result']:
             st.markdown("### ♟️ Grand Master Strategy Report")
             st.markdown(st.session_state['last_audit_result'])
    # ----------------------------------------------
    
    if st.session_state['applied_jobs']:
        st.success(f"You have applied to {len(st.session_state['applied_jobs'])} jobs. Well done!")
    
    # Load from session state (which is loaded from DB)
    applied_dict = st.session_state['applied_jobs']

    # Load persisted Audit Report if not in session
    if 'last_audit_result' not in st.session_state:
        st.session_state['last_audit_result'] = db.load_audit_report()

    
    # --- Live Sync: Enrich Stale Applied Records with Fresh Scouted Data ---
    # This handles the case where "Fetch Details" is run AFTER applying.
    if current_scouted_data:
         scouted_map = {f"{j.get('title')}-{j.get('company')}": j for j in current_scouted_data}
         for jid, data in applied_dict.items():
              if jid in scouted_map:
                   fresh_job = scouted_map[jid]
                   # Update Rich Description if missing
                   curr_details = data.get('job_details', {})
                   existing_rd = curr_details.get('Rich Description') or curr_details.get('rich_description')
                   
                   if (not existing_rd or len(str(existing_rd)) < 20) and fresh_job.get('rich_description'):
                        curr_details['rich_description'] = fresh_job['rich_description']
                        # No explicit disk save to avoid IO lag, but session is updated.
    
    if not applied_dict:
        st.info("No jobs applied yet. Go to Explorer and mark some jobs!")
    else:
        # Construct DF from stored JSON snapshots
        rows = []
        for jid, data in applied_dict.items():
            job_details = data.get('job_details', {})
            row = {
                "Job Title": job_details.get("Job Title", jid.split('-')[0]),
                "Company": job_details.get("Company", jid.split('-')[-1]),
                "Platform": job_details.get("Platform", "Unknown"),
                "Location": job_details.get("Location", "Unknown"),
                "Web Address": job_details.get("Web Address", "#"),
                "Applied Date": data.get("created_at", "").split("T")[0],
                "_full_record": data, # Store full record for access
                "_job_id": jid # Store ID for access
            }
            rows.append(row)
        
        df_applied = pd.DataFrame(rows)
        
        # Create display version without internal data
        display_cols = [c for c in df_applied.columns if not c.startswith("_")]
        df_display = df_applied[display_cols]
        
        event = st.dataframe(
            df_display,
            column_config={
                "Web Address": st.column_config.LinkColumn("Link", display_text="Visit")
            },
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        if event.selection.rows:
            idx = event.selection.rows[0]
            # Retrieve persistent data from source list
            record = rows[idx]["_full_record"]
            job_id = rows[idx]["_job_id"]
            # Extract snapshot analysis
            res = record.get("ai_analysis", {})
            title = rows[idx]["Job Title"]
            
            st.divider()
            st.header(f"💾 Snapshot: {title}")
            
            if not res:
                st.info("Select a job and click Analyze!")
            else:
                # 4 Tabs (Cleaned)
                t1, t2, t5, t6, t7 = st.tabs(["💡 Intel", "📝 Cover Letter", "🎯 ATS Match", "📄 Strategized Resume", "💬 Ask AI"])
                
                with t1:
                    st.subheader("🏢 Deep Intel")
                    intel = res.get("company_intel", {})
                    st.write(f"**Mission**: {intel.get('mission', 'N/A')}")
                    st.markdown("---")
                    xi1, xi2 = st.columns(2)
                    xi1.metric("HQ", intel.get("headquarters", "N/A"))
                    xi2.metric("Size", intel.get("employees", "N/A"))
                    st.metric("Branches", intel.get("branches", "N/A"))
                    st.markdown("**Key Facts**:")
                    for f in intel.get('key_facts', []): st.markdown(f"• {f}")

                with t2:
                     st.subheader("📝 AI Cover Letter")

                     # Humanization Score
                     h_score = res.get("humanization_score", 0)
                     if h_score > 0:
                         st.write(f"**Humanization Level:** {h_score}%")
                         st.progress(h_score / 100)

                     cover_letter = res.get("cover_letter", "No cover letter generated.")
                     st.text_area("Cover Letter", cover_letter, height=500)
                
                with t5:
                    st.subheader("🎯 ATS Match")
                    ats = res.get("ats_report", {})
                    sc = ats.get('score', 0)
                    st.metric("Score", f"{sc}%")
                    st.progress(sc/100)
                    st.write("**You are missing:**")
                    for k in ats.get("missing_skills", []): st.caption(f"❌ {k}")
                
                with t6:
                    st.subheader("📄 Strategized Resume (Experience)")
                    strat_resume = res.get("tailored_resume", "No tailored resume generated.")
                    st.text_area("Tailored Experience", strat_resume, height=500)

                with t7:
                    st.header("Ask AI Interview Guide")
                    
                    # 2-Column Layout: JD (Left) | Resume (Right)
                    col_jd, col_res = st.columns(2)
                    
                    with col_jd:
                        st.subheader("📋 Job Description")
                        jd_source = record.get('job_details', {})
                        jd_text = jd_source.get('Rich Description') or jd_source.get('rich_description') or jd_source.get('Job Description') or jd_source.get('description') or 'No JD available.'
                        st.text_area("JD Content", jd_text, height=500, label_visibility="collapsed")
                        
                    with col_res:
                        st.subheader("📄 Your Resume")
                        
                        # --- Resume Lookup Logic ---
                        job_details_inner = record.get('job_details', {})
                        search_keyword = job_details_inner.get('Found_job', '')
                        
                        # --- Improved Resume Selection ---
                        available_resumes = list(st.session_state['resumes'].keys())
                        matched_resume_data = None
                        
                        # Default logical choice
                        selected_resume_key = None
                        
                        # 1. Try Exact Match
                        if search_keyword and search_keyword in st.session_state['resumes']:
                            selected_resume_key = search_keyword
                        # 2. Try Fuzzy Match
                        else:
                             for rk in available_resumes:
                                 if rk.lower() in search_keyword.lower() or search_keyword.lower() in rk.lower():
                                     selected_resume_key = rk
                                     break
                        
                        # 3. Fallback to First available
                        if not selected_resume_key and available_resumes:
                            selected_resume_key = available_resumes[0]

                        # 4. Selector UI (Allows Override)
                        if available_resumes:
                            selected_resume_key = st.selectbox(
                                "Using Persona:", 
                                available_resumes, 
                                index=available_resumes.index(selected_resume_key) if selected_resume_key in available_resumes else 0,
                                key=f"res_sel_{job_id}"
                            )
                            matched_resume_data = st.session_state['resumes'][selected_resume_key]
                        else:
                             matched_resume_data = None
                        
                        if matched_resume_data and matched_resume_data.get('bytes'):
                            b64_pdf = base64.b64encode(matched_resume_data['bytes']).decode('utf-8')
                            pdf_display = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
                            st.markdown(pdf_display, unsafe_allow_html=True)
                        else:
                            if not matched_resume_data:
                                st.warning(f"Resume for '{search_keyword}' not found in active session. Please re-upload it on Home.")
                            else:
                                st.warning("Resume PDF bytes missing. Re-upload on Home.")
                            
                            # Fallback Text
                            fallback_text = matched_resume_data.get('text', '') if matched_resume_data else ""
                            st.text_area("Resume Content", fallback_text, height=450)

                    st.divider()
                    st.subheader("💬 Chat")

                    # ... Q&A Logic ...
                    if 'qna_history' not in res: res['qna_history'] = []
                    
                    # Display history
                    for msg in res['qna_history']:
                        with st.chat_message(msg["role"]):
                            st.write(msg["content"])
                    
                    # Input
                    q = st.chat_input("Ask a question about this job...")
                    if q:
                        # Append User Msg
                        res['qna_history'].append({"role": "user", "content": q})
                        with st.chat_message("user"): st.write(q)
                        
                        # Generate Answer
                        with st.spinner("Guide is thinking..."):
                             from job_hunter.model_factory import get_llm
                             llm = get_llm()
                             # Context: Job + Resume
                             res_text = matched_resume_data.get('text', '') if matched_resume_data else ""
                             prompt = f"Context:\nJob: {record.get('job_details', {})}\nResume: {res_text[:6000]}\n\nUser Question: {q}\n\nROLE: You are an expert Interview Preparation Guide.\nCONSTRAINT: You must ONLY answer questions directly related to this specific Job Description and the candidate's Resume. If the question is about general world knowledge, code that isn't in the JD, or unrelated topics, refuse to answer.\nAnswer:"
                             ai_msg = llm.invoke(prompt).content
                             
                        # Append AI Msg
                        res['qna_history'].append({"role": "assistant", "content": ai_msg})
                        with st.chat_message("assistant"): st.write(ai_msg)
                        
                        # Save Interaction (Update Cache)
                        st.session_state['job_cache'][job_id] = res
                        db.save_cache(job_id, res)
                        
                        # If already applied, update that record too
                        if job_id in st.session_state['applied_jobs']:
                            curr_app = st.session_state['applied_jobs'][job_id]
                            db.save_applied(job_id, curr_app['job_details'], res, curr_app['status'])
                            
                        st.rerun()

# ==========================================
# VIEW 5: BOT SETTINGS
# ==========================================
if st.session_state['page'] == 'bot_settings':
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
    tab_answers, tab_unknown, tab_add = st.tabs(["📝 My Answers", "❓ Unknown Questions", "➕ Add New"])
    
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
        
        st.divider()
        
        st.markdown("### 📚 Common LinkedIn Questions")
        st.caption("These are typical questions asked during Easy Apply. Click to add them.")
        
        common_qa = [
            ("years of experience", "5"),
            ("how many years", "5"),
            ("authorized to work", "Yes"),
            ("legally authorized", "Yes"),
            ("require sponsorship", "No"),
            ("visa sponsorship", "No"),
            ("willing to relocate", "Yes"),
            ("remote work", "Yes"),
            ("work remotely", "Yes"),
            ("notice period", "2 weeks"),
            ("when can you start", "Immediately"),
            ("start date", "Immediately"),
            ("highest education", "Bachelor's degree"),
            ("proficiency", "Professional"),
            ("english", "Fluent"),
            ("german", "Conversational"),
        ]
        
        for q, a in common_qa:
            if q.lower() not in [k.lower() for k in answers.keys()]:
                c_ex_q, c_ex_a, c_ex_add = st.columns([3, 2, 1])
                c_ex_q.text(q)
                c_ex_a.text(a)
                if c_ex_add.button("➕", key=f"add_ex_{q}"):
                    db.add_answer(q, a)
                    st.toast(f"Added: '{q}' → '{a}'")
                    st.rerun()
