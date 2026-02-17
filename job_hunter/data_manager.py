import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from job_hunter.models import JobRecord
from tools.logger import get_logger

logger = get_logger("DataManager")

DATA_DIR = "data"
SCOUTED_FILE = os.path.join(DATA_DIR, "scouted_jobs.json")
APPLIED_FILE = os.path.join(DATA_DIR, "applied_jobs.json")
PARKED_FILE = os.path.join(DATA_DIR, "parked_jobs.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")
CACHE_FILE = os.path.join(DATA_DIR, "analysis_cache.json")
AUDIT_FILE = os.path.join(DATA_DIR, "career_audit.md")
API_KEYS_FILE = os.path.join(DATA_DIR, "api_keys.json")
BOT_CONFIG_FILE = os.path.join(DATA_DIR, "bot_config.json")
RESUME_HISTORY_FILE = os.path.join(DATA_DIR, "resume_title_history.json")

class DataManager:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        
        default_empty_list = [SCOUTED_FILE, PARKED_FILE]
        for filepath in default_empty_list:
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump([], f)
            
        default_empty_dict = [APPLIED_FILE, CACHE_FILE, API_KEYS_FILE]
        for filepath in default_empty_dict:
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump({}, f)

        if not os.path.exists(BLACKLIST_FILE):
             with open(BLACKLIST_FILE, "w", encoding="utf-8") as f: 
                 json.dump({"companies": [], "titles": [], "safe_phrases": []}, f)

    # --- API KEYS ---
    def load_api_keys(self) -> Dict[str, str]:
        try:
            with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def save_api_key(self, alias: str, key: str) -> Dict[str, str]:
        data = self.load_api_keys()
        data[alias] = key
        with open(API_KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data

    def delete_api_key(self, alias: str) -> Dict[str, str]:
        data = self.load_api_keys()
        if alias in data:
            del data[alias]
            with open(API_KEYS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        return data

    # --- SCOUTED JOBS ---
    def load_scouted(self) -> List[Dict[str, Any]]:
        try:
            with open(SCOUTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def save_scouted_jobs(self, jobs_list: List[Dict[str, Any]], append: bool = False) -> List[Dict[str, Any]]:
        # Convert inputs to JobRecord for normalization
        new_records = [JobRecord.from_dict(j) for j in jobs_list]

        # Filter against applied and parked
        applied = self.load_applied()
        parked = self.load_parked()
        
        applied_ids = set(applied.keys())
        applied_links = {v.get('job_details', {}).get('link') for v in applied.values()}
        parked_ids = {p.get('id') for p in parked}
        parked_links = {p.get('link') for p in parked}

        blacklist = self.load_blacklist()
        bl_companies = [c.lower() for c in blacklist.get("companies", [])]
        bl_titles = [t.lower() for t in blacklist.get("titles", [])]
        safe_phrases = [s.lower() for s in blacklist.get("safe_phrases", [])]

        final_records = []
        for record in new_records:
            jid = record.job_id
            link = record.link
            
            # Blacklist check
            if any(c in record.company.lower() for c in bl_companies):
                continue
            
            if any(t in record.title.lower() for t in bl_titles):
                if not any(s in record.title.lower() for s in safe_phrases):
                    continue

            # Already applied or parked check
            if jid in applied_ids or link in applied_links:
                continue
            if jid in parked_ids or link in parked_links:
                continue
                
            final_records.append(record)

        if append:
            current_raw = self.load_scouted()
            current_records = {JobRecord.from_dict(r).job_id: JobRecord.from_dict(r) for r in current_raw}

            for nr in final_records:
                if nr.job_id in current_records:
                    # Update existing with more detail
                    existing = current_records[nr.job_id]
                    if len(nr.rich_description) > len(existing.rich_description):
                        existing.rich_description = nr.rich_description
                    if nr.language != "Unknown":
                        existing.language = nr.language
                    existing.is_easy_apply = nr.is_easy_apply or existing.is_easy_apply
                    existing.updated_at = datetime.now().isoformat()
                else:
                    current_records[nr.job_id] = nr

            final_data = [r.to_dict() for r in current_records.values()]
        else:
            final_data = [r.to_dict() for r in final_records]

        with open(SCOUTED_FILE, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        return final_data

    def delete_scouted_job(self, title: str, company: str) -> List[Dict[str, Any]]:
        curr = self.load_scouted()
        new_list = [
            x for x in curr 
            if not (x.get('title') == title and x.get('company') == company)
        ]
        with open(SCOUTED_FILE, "w", encoding="utf-8") as f:
            json.dump(new_list, f, indent=2, ensure_ascii=False)
        return new_list

    def archive_applied_jobs(self) -> int:
        scouted = self.load_scouted()
        applied = self.load_applied()
        
        original_count = len(scouted)
        new_scouted = []
        
        for job in scouted:
            record = JobRecord.from_dict(job)
            if record.job_id not in applied:
                new_scouted.append(job)
                
        removed_count = original_count - len(new_scouted)
        if removed_count > 0:
            with open(SCOUTED_FILE, "w", encoding="utf-8") as f:
                json.dump(new_scouted, f, indent=2, ensure_ascii=False)
        return removed_count

    # --- APPLIED JOBS ---
    def load_applied(self) -> Dict[str, Any]:
        try:
            with open(APPLIED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def save_applied(self, job_id: str, job_data: Optional[Dict[str, Any]] = None,
                     analysis_data: Optional[Dict[str, Any]] = None, status: str = "applied") -> Dict[str, Any]:
        data = self.load_applied()
        record = data.get(job_id, {
            "created_at": datetime.now().isoformat(),
            "job_details": {},
            "ai_analysis": {}
        })
        
        record["status"] = status
        record["last_updated"] = datetime.now().isoformat()
        
        if job_data:
            record["job_details"] = JobRecord.from_dict(job_data).to_dict()
        if analysis_data:
            record["ai_analysis"] = analysis_data
        
        data[job_id] = record
        with open(APPLIED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    def delete_applied(self, job_id: str) -> Dict[str, Any]:
        data = self.load_applied()
        if job_id in data:
            del data[job_id]
            with open(APPLIED_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    # --- CACHE ---
    def load_cache(self) -> Dict[str, Any]:
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def save_cache(self, job_id: str, results: Any) -> Dict[str, Any]:
        data = self.load_cache()
        data[job_id] = results
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    # --- PARKED JOBS ---
    def load_parked(self) -> List[Dict[str, Any]]:
        try:
            with open(PARKED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def park_job(self, title: str, company: str, job_data: Optional[Dict[str, Any]] = None) -> bool:
        parked = self.load_parked()
        jid = f"{title}-{company}"
        
        if not any(p.get('id') == jid for p in parked):
            record = {
                "id": jid,
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
        
        self.delete_scouted_job(title, company)
        return True

    # --- BLACKLIST ---
    def load_blacklist(self) -> Dict[str, List[str]]:
        try:
            with open(BLACKLIST_FILE, "r", encoding="utf-8") as f: 
                return json.load(f)
        except:
            return {"companies": [], "titles": [], "safe_phrases": []}

    def save_blacklist(self, companies: List[str], titles: List[str], safe_phrases: List[str] = []) -> Dict[str, List[str]]:
        data = {"companies": companies, "titles": titles, "safe_phrases": safe_phrases}
        with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    # --- AUDIT ---
    def load_audit_report(self) -> str:
        if os.path.exists(AUDIT_FILE):
            try:
                with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                    return f.read()
            except: pass
        return ""

    def save_audit_report(self, markdown_text: str):
        existing = self.load_audit_report()
        new_content = markdown_text + ("\n\n<br>\n\n---\n\n<br>\n\n" + existing if existing else "")
        with open(AUDIT_FILE, "w", encoding="utf-8") as f:
            f.write(new_content)

    # --- BOT CONFIG ---
    def load_bot_config(self) -> Dict[str, Any]:
        default_config = {
            "answers": {
                "years of experience": "3",
                "how many years": "3",
                "work experience": "5",
                "authorized to work": "Yes",
                "require sponsorship": "No",
                "visa sponsorship": "No",
                "willing to relocate": "Yes",
                "remote work": "Yes",
                "notice period": "2 weeks",
                "when can you start": "Immediately",
                "english proficiency": "Professional working proficiency",
                "german proficiency": "Limited working proficiency",
                "highest level of education": "Master's Degree",
                "city": "Berlin",
                "country": "Germany",
                "gender": "Decline to Self-Identify",
                "disability": "No, I do not have a disability",
                "veteran": "No, I am not a protected veteran",
                "ethnicity": "Decline to Self-Identify",
                "race": "Decline to Self-Identify",
            },
            "unknown_questions": []
        }
        if not os.path.exists(BOT_CONFIG_FILE):
            self.save_bot_config(default_config)
            return default_config
        try:
            with open(BOT_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default_config
    
    def save_bot_config(self, config: Dict[str, Any]):
        with open(BOT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def add_answer(self, question_pattern: str, answer: str) -> Dict[str, Any]:
        config = self.load_bot_config()
        q_norm = question_pattern.lower().strip()
        config["answers"][q_norm] = answer
        config["unknown_questions"] = [q for q in config["unknown_questions"] if q.get("question", "").lower() != q_norm]
        self.save_bot_config(config)
        return config
    
    def delete_answer(self, question_pattern: str) -> Dict[str, Any]:
        config = self.load_bot_config()
        q_norm = question_pattern.lower().strip()
        if q_norm in config["answers"]:
            del config["answers"][q_norm]
            self.save_bot_config(config)
        return config
    
    def log_unknown_question(self, question_text: str, job_title: str = "", company: str = ""):
        config = self.load_bot_config()
        q_norm = question_text.lower().strip()
        if any(q.get("question", "").lower() == q_norm for q in config["unknown_questions"]):
            return
        config["unknown_questions"].append({
            "question": question_text.strip(),
            "job_title": job_title,
            "company": company,
            "timestamp": datetime.now().isoformat()
        })
        self.save_bot_config(config)
    
    def clear_unknown_questions(self):
        config = self.load_bot_config()
        config["unknown_questions"] = []
        self.save_bot_config(config)
    
    def get_answer_for_question(self, question_text: str) -> Optional[str]:
        config = self.load_bot_config()
        def normalize(text):
            return re.sub(r'[^\w\s]', '', text.lower()).strip()
        q_norm = normalize(question_text)
        if not q_norm: return None
        
        # Exact match
        for pattern, answer in config["answers"].items():
            if normalize(pattern) == q_norm: return answer

        # Substring match
        for pattern, answer in config["answers"].items():
            p_norm = normalize(pattern)
            if p_norm and (p_norm in q_norm or q_norm in p_norm): return answer

        # Keyword overlap
        q_words = set(q_norm.split())
        best_match, max_overlap = None, 0
        for pattern, answer in config["answers"].items():
            p_words = set(normalize(pattern).split())
            if not p_words: continue
            overlap = len(q_words.intersection(p_words))
            if overlap > max_overlap and (overlap >= 2 or overlap == len(p_words)):
                max_overlap, best_match = overlap, answer
        return best_match
    
    def save_qa_answer(self, question_text: str, answer: str) -> bool:
        self.add_answer(question_text, answer)
        return True
    
    # --- RESUME HISTORY ---
    def load_resume_title_history(self, resume_filename: str) -> List[str]:
        if os.path.exists(RESUME_HISTORY_FILE):
            try:
                with open(RESUME_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f).get(resume_filename, [])
            except: pass
        return []
    
    def save_resume_title_history(self, resume_filename: str, titles: List[str]):
        history = {}
        if os.path.exists(RESUME_HISTORY_FILE):
            try:
                with open(RESUME_HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except: pass
        
        existing = history.get(resume_filename, [])
        combined = []
        for t in (titles + existing):
            t_clean = t.strip()
            if t_clean and t_clean not in combined:
                combined.append(t_clean)
        history[resume_filename] = combined[:50]
        with open(RESUME_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    # --- RESUME CONFIG ---
    def save_resume_config(self, resumes_dict: Dict[str, Any]):
        config_file = os.path.join(DATA_DIR, "resume_config.json")
        config_data = {}
        for role, data in resumes_dict.items():
            config_data[role] = {
                "filename": data.get("filename"),
                "file_path": data.get("file_path"),
                "text": data.get("text"),
                "target_keywords": data.get("target_keywords", "")
            }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

    def load_resume_config(self) -> Dict[str, Any]:
        config_file = os.path.join(DATA_DIR, "resume_config.json")
        resumes = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                for role, data in config_data.items():
                    fpath = data.get("file_path")
                    if fpath and os.path.exists(fpath):
                        with open(fpath, "rb") as f:
                            file_bytes = f.read()
                        resumes[role] = {
                            "filename": data.get("filename"),
                            "file_path": fpath,
                            "text": data.get("text", ""),
                            "bytes": file_bytes,
                            "target_keywords": data.get("target_keywords", "")
                        }
            except Exception as e:
                logger.info(f"Error loading resumes: {e}")
        return resumes

    def save_browser_config(self, user_data_dir: str, profile_name: str):
        from dotenv import set_key
        env_file = ".env"
        if not os.path.exists(env_file):
            with open(env_file, "w") as f: f.write("")
        set_key(env_file, "SYSTEM_CHROME_USER_DATA", user_data_dir)
        set_key(env_file, "SYSTEM_CHROME_PROFILE", profile_name)
        os.environ["SYSTEM_CHROME_USER_DATA"] = user_data_dir
        os.environ["SYSTEM_CHROME_PROFILE"] = profile_name
        return True
