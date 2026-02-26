import json
import os

os.makedirs("data", exist_ok=True)
state = {
    "mission_type": "Scout & Analyze",
    "status": "Scouting Data Analyst on LinkedIn...",
    "phase": "Scouting",
    "current_step": 1,
    "total_steps": 7,
    "current_task_idx": 0,
    "jobs_applied": 0,
    "jobs_scouted": 0,
    "tasks": [
        {"label": "Scrape for Data Analyst in Germany on LinkedIn", "completed": False, "type": "scout"},
        {"label": "Scrape for Data Analyst in Germany on Indeed", "completed": False, "type": "scout"},
        {"label": "Scrape for Data Analyst in Germany on Xing", "completed": False, "type": "scout"},
        {"label": "Scrape for Business Analyst in Germany on LinkedIn", "completed": False, "type": "scout"},
        {"label": "Scrape for Business Analyst in Germany on Indeed", "completed": False, "type": "scout"},
        {"label": "Scrape for Business Analyst in Germany on Xing", "completed": False, "type": "scout"},
        {"label": "Run AI Analysis for 0 Jobs", "completed": False, "type": "analyze"}
    ],
    "is_active": True,
    "is_paused": False,
    "scouting_backlog": [{"keyword": "Data Analyst", "location": "Germany", "platform": "LinkedIn"}],
    "analysis_backlog": [],
    "config_context": {"use_browser_analysis": True}
}

with open("data/mission_state.json", "w") as f:
    json.dump(state, f)
