import json
import os
from datetime import datetime

APPLIED_FILE = "data/applied_jobs.json"
SCOUTED_FILE = "data/scouted_jobs.json"
TARGET_DATE = "2026-02-16"

def repair():
    print(f"🔧 Repairing Data for {TARGET_DATE}...")
    
    if not os.path.exists(APPLIED_FILE):
        print("❌ No applied_jobs.json found.")
        return

    with open(APPLIED_FILE, "r", encoding="utf-8") as f:
        applied_data = json.load(f)
    
    scouted_data = []
    if os.path.exists(SCOUTED_FILE):
        try:
            with open(SCOUTED_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    scouted_data = json.loads(content)
        except: pass

    to_move = []
    
    # Identify jobs to move
    # applied_jobs structure: { "JID": { "applied_date": "...", "job_details": {...} } }
    
    new_applied_data = {}
    
    count = 0
    for jid, entry in applied_data.items():
        date_str = entry.get("created_at", "") or entry.get("last_updated", "") or entry.get("applied_date", "")
        
        if "2026-02-15" in date_str or "2026-02-16" in date_str:
             if count < 5:
                 print(f"FOUND: {jid[:20]}... -> {date_str}")
             scouted_data.append(entry.get("job_details", {}))
             to_move.append(jid)
             count += 1
        else:
            new_applied_data[jid] = entry
            
    # Save back
    with open(APPLIED_FILE, "w", encoding="utf-8") as f:
        json.dump(new_applied_data, f, indent=4)
        
    with open(SCOUTED_FILE, "w", encoding="utf-8") as f:
        json.dump(scouted_data, f, indent=4)
        
    print(f"✅ Moved {len(to_move)} jobs from Applied to Scouted.")
    print(f"   Applied Count: {len(applied_data)} -> {len(new_applied_data)}")
    print(f"   Scouted Count: {len(scouted_data) - len(to_move)} -> {len(scouted_data)}")

if __name__ == "__main__":
    repair()
