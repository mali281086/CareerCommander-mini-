import json
import os
from datetime import datetime

DATA_DIR = "data"
SCOUTED_FILE = os.path.join(DATA_DIR, "scouted_jobs.json")
APPLIED_FILE = os.path.join(DATA_DIR, "applied_jobs.json")
PARKED_FILE = os.path.join(DATA_DIR, "parked_jobs.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")
CACHE_FILE = os.path.join(DATA_DIR, "analysis_cache.json")
AUDIT_FILE = os.path.join(DATA_DIR, "career_audit.md")

class DataManager:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        
        # Scouted: LIST of job dicts
        if not os.path.exists(SCOUTED_FILE):
            with open(SCOUTED_FILE, "w", encoding="utf-8") as f: json.dump([], f)
            
        # Applied: DICT keyed by job_id
        if not os.path.exists(APPLIED_FILE):
            with open(APPLIED_FILE, "w", encoding="utf-8") as f: json.dump({}, f)
            
        if not os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump({}, f)

        # Parked: LIST of parked job IDs/Metadata
        if not os.path.exists(PARKED_FILE):
            with open(PARKED_FILE, "w", encoding="utf-8") as f: json.dump([], f)

        # Blacklist: DICT
        if not os.path.exists(BLACKLIST_FILE):
             with open(BLACKLIST_FILE, "w", encoding="utf-8") as f: 
                 json.dump({"companies": [], "titles": []}, f)

    # --- API KEYS ---
    def load_api_keys(self):
        """Returns dict of {Alias: Key}"""
        keys_file = os.path.join(DATA_DIR, "api_keys.json")
        if not os.path.exists(keys_file):
             return {}
        try:
            with open(keys_file, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}

    def save_api_key(self, alias, key):
        keys_file = os.path.join(DATA_DIR, "api_keys.json")
        data = self.load_api_keys()
        data[alias] = key
        with open(keys_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
        return data

    def delete_api_key(self, alias):
        keys_file = os.path.join(DATA_DIR, "api_keys.json")
        data = self.load_api_keys()
        if alias in data:
            del data[alias]
            with open(keys_file, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
        return data

    # --- SCOUTED JOBS ---
    def load_scouted(self):
        try:
            with open(SCOUTED_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []

    def save_scouted_jobs(self, jobs_list, append=False):
        """
        Saves a list of job dictionaries.
        If append is True, adds to existing.
        If append is False, OVERWRITES (fresh search).
        """
        # --- FILTER: Remove Already Applied Jobs ---
        applied = self.load_applied()
        applied_ids = set(applied.keys())
        applied_links = set()
        for v in applied.values():
             details = v.get('job_details', {})
             # Collect various link keys just in case
             lnk = details.get('Web Address') or details.get('link') or details.get('url')
             if lnk: applied_links.add(lnk)

        filtered_list = []

        # --- LOAD PARKED JOBS TO IGNORE ---
        parked = self.load_parked()
        parked_ids = set()
        parked_links = set()

        for p in parked:
            # Reconstruct IDs or use saved ones
            p_id = p.get('id')
            if p_id: parked_ids.add(p_id)
            if p.get('link'): parked_links.add(p.get('link'))
            # Also support Title-Company matching from parked entries
            if p.get('title') and p.get('company'):
                parked_ids.add(f"{p['title']}-{p['company']}")
        # ----------------------------------

        # ----------------------------------

        # --- LOAD BLACKLIST & SAFE WORDS ---
        blacklist = self.load_blacklist()
        bl_companies = [c.lower() for c in blacklist.get("companies", []) if c]
        bl_titles = [t.lower() for t in blacklist.get("titles", []) if t]
        safe_phrases = [s.lower() for s in blacklist.get("safe_phrases", []) if s]
        # ----------------------

        # STEP 1: SEGREGATE (Potential Survivors vs Blacklisted Candidates)
        potential_survivors = []
        blacklisted_candidates = [] # Temp cache as requested

        for job in jobs_list:
             j_title = job.get('title', 'Unknown').lower()
             j_company = job.get('company', 'Unknown').lower()
             
             # Check Company Blacklist first (always drops? User didn't specify safe for company, but implied safe for title)
             # Let's assume Safe applies to Title primarily.
             is_bad_company = False
             for bl_c in bl_companies:
                  if bl_c in j_company: 
                      is_bad_company = True
                      break
             
             if is_bad_company:
                 # Company ban is usually absolute? User said "scraping should drop jobs from those companies".
                 # So we drop them entirely, usually no rescue for bad company.
                 continue

             # Check Title Blacklist
             is_bad_title = False
             for bl_t in bl_titles:
                 if bl_t in j_title:
                     is_bad_title = True
                     break
             
             if is_bad_title:
                 blacklisted_candidates.append(job)
             else:
                 potential_survivors.append(job)

        # STEP 2: RESCUE MISSION (Safe Phrases)
        rescued_jobs = []
        if safe_phrases:
            for job in blacklisted_candidates:
                j_title = job.get('title', '').lower()
                is_safe = False
                for safe in safe_phrases:
                    # Check if safe word exists in title
                    if safe in j_title:
                        is_safe = True
                        break
                
                if is_safe:
                    rescued_jobs.append(job)
        
        # Merge Survivors and Rescued
        final_candidates = potential_survivors + rescued_jobs

        # STEP 3: FINAL APPLIED/PARKED CHECK
        filtered_list = []
        for job in final_candidates:
             j_title = job.get('title', 'Unknown')
             j_company = job.get('company', 'Unknown')
             jid = f"{j_title}-{j_company}" # Normalization happens in app logic mostly, but here we construct ID
             j_link = job.get('link')

             if jid in applied_ids: continue
             if j_link and j_link in applied_links: continue
             
             if jid in parked_ids: continue
             if j_link and j_link in parked_links: continue
             
             filtered_list.append(job)
             
        jobs_list = filtered_list  
        # -------------------------------------------

        if append:
            current = self.load_scouted()
            
            # --- DEDUPLICATION STRATEGY ---
            # 1. By Link
            existing_links = {j.get('link') for j in current if j.get('link')}
            # 2. By Composite Key (Title-Company) - normalized
            # storing as tuple: (title.lower(), company.lower())
            existing_composites = set()
            for j in current:
                t = j.get('title', '').strip().lower()
                c = j.get('company', '').strip().lower()
                if t and c:
                    existing_composites.add((t, c))
            
            for job in jobs_list:
                link = job.get('link')
                
                # Check 1: Link Existence
                if link and link in existing_links:
                    continue # Duplicate by link
                
                # Check 2: Composite Existence
                t_new = job.get('title', '').strip().lower()
                c_new = job.get('company', '').strip().lower()
                if (t_new, c_new) in existing_composites:
                    continue # Duplicate by Title+Company
                
                # If unique, add it
                current.append(job)
                
                # Update tracking sets
                if link: existing_links.add(link)
                if t_new and c_new: existing_composites.add((t_new, c_new))

            final_data = current
        else:
            final_data = jobs_list

        with open(SCOUTED_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        return final_data

    def delete_scouted_job(self, title, company):
        """
        CASCADE DELETES a job from ALL records (Scouted, Applied, Cache) based on Title and Company.
        """
        # 1. SCOUTED
        curr = self.load_scouted()
        job_id = f"{title}-{company}" # Construct ID
        
        new_list = [
            x for x in curr 
            if not (x.get('title') == title and x.get('company') == company)
        ]
        
        with open(SCOUTED_FILE, "w", encoding="utf-8") as f:
            json.dump(new_list, f, indent=2, ensure_ascii=False)
            
        return new_list

    def archive_applied_jobs(self):
        """
        Removes jobs from 'scouted_jobs.json' that are present in 'applied_jobs.json'.
        Returns the number of jobs removed (archived).
        """
        scouted = self.load_scouted()
        applied = self.load_applied()
        
        # Identify jobs to keep (those NOT in applied)
        # Using composite key Title-Company as ID
        # applied_keys = set(applied.keys()) 
        # But applied keys are generated strings. 
        # DataManager.save_applied uses job_id passed to it. 
        # In app.py, job_id = f"{row['Job Title']}-{row['Company']}"
        
        # So we can reconstruct keys from scouted to check existence
        
        original_count = len(scouted)
        new_scouted = []
        
        for job in scouted:
            # Reconstruct ID
            # Note: Startup normalization in app.py renames keys, but raw json has 'title', 'company'
            # We must use raw keys here.
            j_title = job.get('title', 'Unknown')
            j_company = job.get('company', 'Unknown')
            job_id = f"{j_title}-{j_company}"
            
            if job_id not in applied:
                new_scouted.append(job)
                
        removed_count = original_count - len(new_scouted)
        
        if removed_count > 0:
            with open(SCOUTED_FILE, "w", encoding="utf-8") as f:
                json.dump(new_scouted, f, indent=2, ensure_ascii=False)
                
        return removed_count
        applied = self.load_applied()
        if job_id in applied:
            del applied[job_id]
            with open(APPLIED_FILE, "w", encoding="utf-8") as f: json.dump(applied, f, indent=2, ensure_ascii=False)
            
        # 3. CACHE
        cache = self.load_cache()
        if job_id in cache:
            del cache[job_id]
            with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump(cache, f, indent=2, ensure_ascii=False)
            
        return new_list

    # --- APPLIED JOBS ---
    def load_applied(self):
        try:
            with open(APPLIED_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}

    def save_applied(self, job_id, job_data=None, analysis_data=None, status="applied"):
        data = self.load_applied()
        
        # Merge if exists
        record = data.get(job_id, {
            "created_at": datetime.now().isoformat(),
            "job_details": {},
            "ai_analysis": {}
        })
        
        record["status"] = status
        record["last_updated"] = datetime.now().isoformat()
        
        if job_data: record["job_details"] = job_data
        if analysis_data: record["ai_analysis"] = analysis_data
        
        data[job_id] = record
        with open(APPLIED_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    def delete_applied(self, job_id):
        data = self.load_applied()
        if job_id in data:
            del data[job_id]
            with open(APPLIED_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    # --- CACHE (AI Results) ---
    def load_cache(self):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}

    def save_cache(self, job_id, results):
        data = self.load_cache()
        data[job_id] = results
        with open(CACHE_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    # --- PARKED JOBS ---
    def load_parked(self):
        try:
            with open(PARKED_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []

    def park_job(self, title, company, job_data=None):
        """
        Moves a job from SCOUTED to PARKED.
        """
        # 1. Add to Parked
        parked = self.load_parked()
        
        # Check if already parked
        exists = False
        for p in parked:
            if p.get('title') == title and p.get('company') == company:
                exists = True
                break
        
        if not exists:
            # Construct minimal or full record
            record = {
                "id": f"{title}-{company}",
                "title": title,
                "company": company,
                "parked_at": datetime.now().isoformat()
            }
            if job_data:
                record['link'] = job_data.get('link') or job_data.get('Web Address')
                record['platform'] = job_data.get('platform') or job_data.get('Platform')
                
            parked.append(record)
            with open(PARKED_FILE, "w", encoding="utf-8") as f:
                json.dump(parked, f, indent=2, ensure_ascii=False)
        
        # 2. Remove from Scouted
        self.delete_scouted_job(title, company)
        return True
        return True

    # --- BLACKLIST ---
    def load_blacklist(self):
        try:
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f: 
                data = json.load(f)
                if "safe_phrases" not in data: data["safe_phrases"] = []
                return data
        except: return {"companies": [], "titles": [], "safe_phrases": []}

    def save_blacklist(self, companies, titles, safe_phrases=[]):
        data = {"companies": companies, "titles": titles, "safe_phrases": safe_phrases}
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    # --- CAREER AUDIT PERSISTENCE ---
    def load_audit_report(self):
        try:
            if os.path.exists(AUDIT_FILE):
                with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                    return f.read()
            return ""
        except: return ""

    def save_audit_report(self, markdown_text):
        # "Logbook" Mode: Prepend new report to existing history
        existing = ""
        if os.path.exists(AUDIT_FILE):
             try:
                 with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                     existing = f.read()
             except: pass
        
        # Add a separator if there's existing content
        if existing:
            new_content = markdown_text + "\n\n<br>\n\n---\n\n<br>\n\n" + existing
        else:
            new_content = markdown_text

        with open(AUDIT_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)


