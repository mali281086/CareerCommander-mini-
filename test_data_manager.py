from job_hunter.data_manager import DataManager
import os
import json

db = DataManager()
# Clear scouted
with open("data/scouted_jobs.json", "w") as f: json.dump([], f)

# 1. Add shallow job
job1 = {"title": "Engineer", "company": "Tech", "link": "http://example.com/1", "location": "Berlin"}
db.save_scouted_jobs([job1], append=True)

with open("data/scouted_jobs.json", "r") as f:
    data = json.load(f)
    print("Initial:", data[0].get("rich_description"), data[0].get("language"))

# 2. Add deep version of same job
job1_deep = {"title": "Engineer", "company": "Tech", "link": "http://example.com/1", "rich_description": "Deep Details...", "language": "en"}
db.save_scouted_jobs([job1_deep], append=True)

with open("data/scouted_jobs.json", "r") as f:
    data = json.load(f)
    print("After Deep Scrape:", data[0].get("rich_description"), data[0].get("language"))
    print("Length:", len(data))
