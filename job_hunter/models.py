from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class JobRecord:
    """Standardized job data model."""
    title: str
    company: str
    location: str
    link: str
    platform: str
    is_easy_apply: bool = False
    language: str = "en"
    description: str = ""
    rich_description: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the record to a dictionary for JSON storage."""
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "link": self.link,
            "platform": self.platform,
            "is_easy_apply": self.is_easy_apply,
            "language": self.language,
            "description": self.description,
            "rich_description": self.rich_description,
            "scraped_at": self.scraped_at,
            **self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobRecord':
        """Creates a JobRecord from a dictionary."""
        # Extract known fields
        known_fields = {
            "title": data.get("title") or data.get("Job Title", "Unknown"),
            "company": data.get("company") or data.get("Company", "Unknown"),
            "location": data.get("location") or data.get("Location", "Unknown"),
            "link": data.get("link") or data.get("Web Address", ""),
            "platform": data.get("platform") or data.get("Platform", "Unknown"),
            "is_easy_apply": data.get("is_easy_apply") or data.get("Easy Apply", False),
            "language": data.get("language") or data.get("Language", "en"),
            "description": data.get("description") or data.get("Job Description", ""),
            "rich_description": data.get("rich_description", ""),
            "scraped_at": data.get("scraped_at") or datetime.now().isoformat()
        }

        # Remaining data goes into metadata
        metadata = {k: v for k, v in data.items() if k not in known_fields and k not in ["Job Title", "Company", "Location", "Web Address", "Platform", "Easy Apply", "Language", "Job Description"]}

        return cls(**known_fields, metadata=metadata)
