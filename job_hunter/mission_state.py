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
    current_step: int = 0
    total_steps: int = 0
    jobs_applied: int = 0
    jobs_scouted: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    last_update: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = False
    pending_question: Optional[str] = None

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
        self.status = "Idle"
        self.current_step = 0
        self.total_steps = 0
        self.jobs_applied = 0
        self.jobs_scouted = 0
        self.errors = []
        self.pending_question = None
        self.save()
