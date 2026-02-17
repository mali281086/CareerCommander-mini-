import time
import random
import streamlit as st
from job_hunter.scout import Scout
from job_hunter.applier import JobApplier
from job_hunter.analysis_crew import JobAnalysisCrew
from job_hunter.data_manager import DataManager
from tools.browser_manager import BrowserManager
from tools.logger import get_logger

logger = get_logger("MissionManager")

class MissionManager:
    def __init__(self, db: DataManager):
        self.db = db

    def run_live_apply(self, resumes, location, limit, platforms, use_browser_analysis, status_box):
        total_applied = 0
        total_skipped = 0
        total_errors = 0
        all_unknown = []

        # Instantiate applier with the first available resume (as original app did)
        resume_path = None
        if resumes:
            first_role = list(resumes.values())[0]
            resume_path = first_role.get('file_path')

        applier = JobApplier(resume_path=resume_path)
        scout = Scout()

        search_queue = []
        for role_name, data in resumes.items():
            kw_list = [k.strip() for k in data.get('target_keywords', '').split(';') if k.strip()] or [role_name]
            self.db.save_resume_title_history(data.get('filename', role_name), kw_list)

            loc_list = [l.strip() for l in location.split(';') if l.strip()] or ["Germany"]
            for kw in kw_list:
                for loc in loc_list:
                    search_queue.append({"keyword": kw, "location": loc, "role": role_name})

        for p in platforms:
            status_box.caption(f"🌍 Switching to {p}...")
            for item in search_queue:
                status_box.info(f"🔍 Scouting '{item['keyword']}' on {p}...")
                try:
                    scouted = scout.launch_mission(
                        keyword=item['keyword'], location=item['location'], limit=limit,
                        platforms=[p], easy_apply=True, deep_scrape=False
                    )

                    if not scouted: continue

                    status_box.info(f"🎯 Found {len(scouted)} candidates on {p}. Applying...")
                    for job in scouted:
                        success, msg, is_easy = applier.apply(
                            job_url=job.get('link'), platform=p, skip_detection=True,
                            job_title=job.get('title'), company=job.get('company'),
                            target_role=item['role']
                        )
                        if success:
                            total_applied += 1
                            jid = f"{job.get('title')}-{job.get('company')}"
                            self.db.save_applied(jid, job, {"auto_applied": True})
                            st.toast(f"✅ Applied: {job.get('title')}")
                        else:
                            if not is_easy: total_skipped += 1
                            else: total_errors += 1

                except Exception as e:
                    logger.error(f"Error in live apply for {item['keyword']} on {p}: {e}")
                    st.error(f"Failed for {item['keyword']} on {p}")

        applier.close()
        self.db.archive_applied_jobs()
        return total_applied, total_skipped, total_errors, all_unknown

    def run_standard_scrape(self, resumes, location, limit, platforms, deep_scrape, use_browser_analysis, status_box):
        scout = Scout()
        all_results = []

        for role_name, data in resumes.items():
            kw_list = [k.strip() for k in data.get('target_keywords', '').split(';') if k.strip()] or [role_name]
            self.db.save_resume_title_history(data.get('filename', role_name), kw_list)

            loc_list = [l.strip() for l in location.split(';') if l.strip()] or ["Germany"]
            for kw in kw_list:
                for loc in loc_list:
                    status_box.info(f"🚀 Scouting '{kw}' in '{loc}'...")
                    try:
                        res = scout.launch_mission(
                            keyword=kw, location=loc, limit=limit, platforms=platforms,
                            easy_apply=False, deep_scrape=deep_scrape,
                            status_callback=lambda m: status_box.info(f"🚀 {m}")
                        )
                        for r in res:
                            r['_resume_text'] = data.get('text', '')
                            r['_role_name'] = role_name
                        all_results.extend(res)
                    except Exception as e:
                        logger.error(f"Scout failed for {kw}: {e}")

        if all_results:
            self._run_automated_analysis(all_results, use_browser_analysis, status_box)
        return all_results

    def _run_automated_analysis(self, jobs, use_browser, status_box):
        unique_jobs = {}
        for j in jobs:
            jid = f"{j.get('title')}-{j.get('company')}"
            if jid not in unique_jobs: unique_jobs[jid] = j

        jobs_to_analyze = list(unique_jobs.values())
        total = len(jobs_to_analyze)
        status_box.info(f"🧠 AI Analysis for {total} jobs...")

        cache = self.db.load_cache()
        prog = st.progress(0)

        for i, job in enumerate(jobs_to_analyze):
            jid = f"{job.get('title')}-{job.get('company')}"
            if jid in cache:
                prog.progress((i+1)/total)
                continue

            desc = job.get('rich_description') or job.get('description') or ""
            if len(desc) > 50:
                try:
                    status_box.info(f"🧠 Analyzing [{i+1}/{total}]: {job.get('title')}...")
                    context = f"Title: {job.get('title')}\nCompany: {job.get('company')}\nJD:\n{desc}"
                    crew = JobAnalysisCrew(context, job.get('_resume_text', ''))
                    results = crew.run_analysis(use_browser=use_browser)
                    if results and "error" not in results:
                        self.db.save_cache(jid, results)
                        if 'job_cache' in st.session_state:
                            st.session_state['job_cache'][jid] = results
                except Exception as e:
                    logger.error(f"Analysis failed for {jid}: {e}")

            prog.progress((i+1)/total)
            if use_browser: time.sleep(random.uniform(2, 4))

        BrowserManager().close_all_drivers()
