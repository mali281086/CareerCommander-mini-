from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class JobRecord:
    title: str
    company: str
    location: str
    link: str
    platform: str
    is_easy_apply: bool = False
    description: str = ""
    rich_description: str = ""
    language: str = "Unknown"
    search_keyword: str = "Unknown"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def job_id(self) -> str:
        return f"{self.title}-{self.company}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobRecord":
        # Handle renames from old format or UI labels
        mapping = {
            "Job Title": "title",
            "Job_Title": "title",
            "Job title": "title",
            "Web Address": "link",
            "Web_address": "link",
            "Web address": "link",
            "Found_job": "search_keyword",
            "Found_Job": "search_keyword",
            "Found job": "search_keyword",
            "Easy Apply": "is_easy_apply",
            "Easy_Apply": "is_easy_apply",
            "Easy apply": "is_easy_apply",
            "Job Description": "description",
            "Job_Description": "description",
            "Job description": "description",
            "Rich Description": "rich_description",
            "Rich_Description": "rich_description",
            "Rich description": "rich_description"
        }

        # Normalize keys
        normalized = {}
        for k, v in data.items():
            # Try mapping first, then snake_case, then original
            new_key = mapping.get(k, k.lower().replace(" ", "_"))
            normalized[new_key] = v

        # Ensure only valid fields are passed to constructor
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in normalized.items() if k in valid_fields}

        # Fallback for missing required fields
        if "title" not in filtered: filtered["title"] = data.get("title", "Unknown")
        if "company" not in filtered: filtered["company"] = data.get("company", "Unknown")
        if "location" not in filtered: filtered["location"] = data.get("location", "Unknown")
        if "link" not in filtered: filtered["link"] = data.get("link", "Unknown")
        if "platform" not in filtered: filtered["platform"] = data.get("platform", "Unknown")

        return cls(**filtered)
