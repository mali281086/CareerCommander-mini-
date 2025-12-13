import streamlit as st
import pandas as pd
import json
import os
import glob
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="CareerCommander",
    page_icon="🎖️",
    layout="wide"
)

# Title and Header
st.title("🎖️ CareerCommander")
st.markdown("### Take command of your career with AI.")

# Data Loading Function
@st.cache_data
def load_data():
    all_jobs = []
    # Load all JSON files in data directory to be robust
    json_files = glob.glob(os.path.join("data", "*.json"))
    
    for file in json_files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_jobs.extend(data)
        except Exception as e:
            st.error(f"Error loading {file}: {e}")
            
    if not all_jobs:
        return pd.DataFrame()
        
    df = pd.DataFrame(all_jobs)
    return df

# Load Data
df = load_data()

# Clean Data if exists
if not df.empty:
    if "Platform" not in df.columns:
        df["Platform"] = "Unknown"
    else:
        df["Platform"] = df["Platform"].fillna("Unknown").astype(str)

    if "Location" not in df.columns:
        df["Location"] = "Unknown"
    else:
        df["Location"] = df["Location"].fillna("Unknown").astype(str)

# Sidebar
with st.sidebar:
    st.markdown("**Scrapers Status:**")
    st.success("Configured")
    st.markdown("---")

    st.header("Filters")
    
    # Platform Selection (Used for both Filtering and Scraping)
    platforms = ["Indeed", "Stepstone", "Xing", "ZipRecruiter"]
    selected_platforms = st.multiselect("Select Platform(s)", platforms, default=platforms)
    
    st.markdown("---")
    st.markdown("**1. Scraper Settings**")
    
    # Scraper Inputs
    scrape_keyword = st.text_input("Job Title to Scrape", value="Data Analyst")
    scrape_location = st.text_input("Location to Scrape", value="Germany")
    scrape_limit = st.number_input("Max Jobs per Platform", min_value=1, max_value=1000, value=50, step=10)

    # Start Search Button
    if st.button("Start Search"):
        if not scrape_keyword:
            st.error("Please enter a Job Title.")
        else:
            with st.spinner(f"Scraping jobs for '{scrape_keyword}' in '{scrape_location}'..."):
                import subprocess
                import sys
                
                platforms_arg = selected_platforms if selected_platforms else ["All"]
                
                cmd = [
                    sys.executable, 
                    "run_search.py", 
                    "--keyword", scrape_keyword, 
                    "--location", scrape_location if scrape_location else "",
                    "--limit", str(scrape_limit),
                    "--platforms"
                ] + platforms_arg
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        st.success("Scraping completed!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Scraping failed.")
                        st.code(result.stderr)
                except Exception as e:
                    st.error(f"Failed to run scrapers: {e}")

    st.markdown("---")
    st.markdown("**2. View Filters**")

    # View Filters
    filter_keyword = st.text_input("Filter Results by Keyword", "")
    filter_location = st.text_input("Filter Results by Location", "")

# Main Content
if df.empty:
    st.warning("No data found in `data/`. Run the scrapers first!")
else:
    # Ensure Date Extracted exists
    if "Date Extracted" not in df.columns:
        df["Date Extracted"] = "Unknown"

    # Metrics Container
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Jobs Found", len(df))
    col2.metric("Platforms", df["Platform"].nunique())
    col3.metric("Companies", df["Company"].nunique())
    
    # Platform Breakdown
    st.markdown("### Platform Breakdown")
    p_cols = st.columns(4)
    
    # Calculate counts
    counts = df["Platform"].value_counts()
    
    p_cols[0].metric("Indeed", counts.get("Indeed", 0))
    p_cols[1].metric("Stepstone", counts.get("Stepstone", 0))
    p_cols[2].metric("Xing", counts.get("Xing", 0))
    p_cols[3].metric("ZipRecruiter", counts.get("ZipRecruiter", 0))

    st.markdown("---")

    # Apply Filters
    filtered_df = df.copy()
    
    if selected_platforms:
        filtered_df = filtered_df[filtered_df["Platform"].isin(selected_platforms)]

    if filter_location:
        filtered_df = filtered_df[filtered_df["Location"].str.contains(filter_location, case=False, na=False)]
        
    if filter_keyword:
        filtered_df = filtered_df[filtered_df["Job Title"].str.contains(filter_keyword, case=False, na=False)]

    # Data Display
    st.subheader("Job Explorer")
    
    # Display as a dataframe with clickable links configuration
    st.dataframe(
        filtered_df,
        column_config={
            "Web Address": st.column_config.LinkColumn("Apply Link"),
            "Job Title": st.column_config.TextColumn("Job Title", width="large"),
            "Company": st.column_config.TextColumn("Company", width="medium"),
            "Location": st.column_config.TextColumn("Location", width="medium"),
            "Platform": st.column_config.TextColumn("Platform", width="small"),
            "Date Extracted": st.column_config.TextColumn("Date Found", width="small"),
        },
        use_container_width=True,
        hide_index=True
    )

    # Raw Data View (Optional)
    with st.expander("View Raw JSON Data"):
        st.json(filtered_df.to_dict(orient="records"))