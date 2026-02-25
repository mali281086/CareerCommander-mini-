import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime

STATE_FILE = "data/mission_state.json"

@dataclass
class MissionProgress:
    mission_type: str  # "Live Apply", "Batch Apply", "Scout & Analyze"
    status: str = "Idle"
    phase: str = "None" # "Scouting", "Analysis", "Applying"
    current_step: int = 0
    total_steps: int = 0
    jobs_applied: int = 0
    jobs_scouted: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    last_update: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = False
    is_paused: bool = False
    pending_question: Optional[str] = None
    pending_decision: Optional[str] = None # For "Skip or Retry" prompts

    # Roadmap of tasks
    tasks: List[dict] = field(default_factory=list) # [{"label": str, "completed": bool, "type": str}]

    # Backlog of work to allow resumption
    scouting_backlog: List[dict] = field(default_factory=list) # [{kw, loc, platform, role_name, resume_text}]
    analysis_backlog: List[dict] = field(default_factory=list) # List of scouted job dicts

    # Context for resumption
    config_context: dict = field(default_factory=dict) # Store scrape_limit, deep_scrape_toggle etc.

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_update = datetime.now().isoformat()
        self.save()

    def save(self):
        os.makedirs("data", exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls(**data)
            except:
                pass
        return cls(mission_type="None")

    def reset(self):
        self.is_active = False
        self.is_paused = False
        self.status = "Idle"
        self.phase = "None"
        self.current_step = 0
        self.total_steps = 0
        self.jobs_applied = 0
        self.jobs_scouted = 0
        self.errors = []
        self.pending_question = None
        self.pending_decision = None
        self.tasks = []
        self.scouting_backlog = []
        self.analysis_backlog = []
        self.config_context = {}
        self.save()
