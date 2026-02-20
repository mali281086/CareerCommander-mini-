from dataclasses import dataclass, field
from typing import Dict, Any
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
