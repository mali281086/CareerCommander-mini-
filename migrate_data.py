import os
import json
from datetime import datetime
from job_hunter.models import JobRecord

DATA_DIR = "data"
SCOUTED_FILE = os.path.join(DATA_DIR, "scouted_jobs.json")
APPLIED_FILE = os.path.join(DATA_DIR, "applied_jobs.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

def backup_file(filepath):
    if not os.path.exists(filepath):
        return
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    filename = os.path.basename(filepath)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"{filename}.{timestamp}.bak")

    import shutil
    shutil.copy2(filepath, backup_path)
    print(f"Backed up {filename} to {backup_path}")

def migrate_scouted():
    if not os.path.exists(SCOUTED_FILE):
        print(f"No scouted jobs file found at {SCOUTED_FILE}")
        return

    backup_file(SCOUTED_FILE)

    with open(SCOUTED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"Error: {SCOUTED_FILE} is not a list")
        return

    migrated = []
    for item in data:
        record = JobRecord.from_dict(item)
        migrated.append(record.to_dict())

    with open(SCOUTED_FILE, "w", encoding="utf-8") as f:
        json.dump(migrated, f, indent=2, ensure_ascii=False)
    print(f"Migrated {len(migrated)} jobs in {SCOUTED_FILE}")

def migrate_applied():
    if not os.path.exists(APPLIED_FILE):
        print(f"No applied jobs file found at {APPLIED_FILE}")
        return

    backup_file(APPLIED_FILE)

    with open(APPLIED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print(f"Error: {APPLIED_FILE} is not a dict")
        return

    migrated = {}
    for jid, entry in data.items():
        if "job_details" in entry:
            entry["job_details"] = JobRecord.from_dict(entry["job_details"]).to_dict()
        migrated[jid] = entry

    with open(APPLIED_FILE, "w", encoding="utf-8") as f:
        json.dump(migrated, f, indent=2, ensure_ascii=False)
    print(f"Migrated {len(migrated)} entries in {APPLIED_FILE}")

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created {DATA_DIR} directory")

    migrate_scouted()
    migrate_applied()
    print("Migration complete!")
