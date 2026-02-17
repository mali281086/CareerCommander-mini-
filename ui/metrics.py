import streamlit as st
import pandas as pd
from datetime import datetime
import altair as alt

def render_metrics_dashboard(current_df, applied_dict, parked_count=0):
    """
    Renders Dashboard 2.1: Cards on Top, Stacked Timeline, Toggle-only.
    """

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
    view_by = c_view.radio("View Charts By:", ["Target Role", "Platform", "Language"], horizontal=True, label_visibility="collapsed")

    if view_by == "Target Role":
        group_col = "Found_job"
    elif view_by == "Platform":
        group_col = "Platform"
    else:
        group_col = "Language"

    # --- 3. PIE CHARTS ---
    st.markdown("##### Distribution")

    # Check if selected column exists in dataframes
    current_has_col = group_col in current_df.columns if not current_df.empty else False
    applied_has_col = group_col in applied_df.columns if not applied_df.empty else False

    # Prepare Data
    if not current_df.empty and current_has_col:
        curr_counts = current_df[group_col].fillna("Unknown").value_counts().reset_index()
        curr_counts.columns = ['Label', 'Count']
    else:
        curr_counts = pd.DataFrame(columns=['Label', 'Count'])

    if not applied_df.empty and applied_has_col:
        app_counts = applied_df[group_col].fillna("Unknown").value_counts().reset_index()
        app_counts.columns = ['Label', 'Count']
    else:
        app_counts = pd.DataFrame(columns=['Label', 'Count'])

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
            if view_by == "Language":
                st.info("No language data. Run 'Fetch Complete Details' first.")
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
            if view_by == "Language":
                st.info("No language data available.")
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
