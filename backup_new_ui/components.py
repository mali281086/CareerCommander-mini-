import streamlit as st
import pandas as pd
from datetime import datetime

def render_metrics_dashboard(current_df, applied_dict, parked_count=0):
    applied_rows = []
    for jid, data in applied_dict.items():
        details = data.get('job_details', {})
        applied_rows.append({
            "Platform": details.get('Platform', 'Unknown'),
            "created_at": data.get('created_at', datetime.now().isoformat())
        })
    applied_df = pd.DataFrame(applied_rows)

    count_scouted = len(current_df)
    count_applied = len(applied_df)

    avg_msg = "N/A"
    if not applied_df.empty:
        dates = pd.to_datetime(applied_df['created_at'])
        days_diff = (datetime.now().date() - dates.min().date()).days + 1
        avg_msg = f"{len(applied_df) / max(1, days_diff):.1f}"

    def card(label, value):
        return f"""
        <div style="background-color: #262730; padding: 15px; border-radius: 8px; border: 1px solid #41424C; text-align: center;">
            <p style="font-size: 0.8em; color: #aaaaaa; margin-bottom: 5px;">{label}</p>
            <h3 style="margin: 0; color: white;">{value}</h3>
        </div>
        """

    cols = st.columns(5)
    cols[0].markdown(card("Current Jobs", count_scouted), unsafe_allow_html=True)
    cols[1].markdown(card("Applied Jobs", count_applied), unsafe_allow_html=True)
    cols[2].markdown(card("Parked Jobs", parked_count), unsafe_allow_html=True)
    cols[3].markdown(card("Total Jobs", count_scouted + count_applied + parked_count), unsafe_allow_html=True)
    cols[4].markdown(card("Avg Applied/Day", avg_msg), unsafe_allow_html=True)
