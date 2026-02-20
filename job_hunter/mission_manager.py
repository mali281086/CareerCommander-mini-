import streamlit as st
import time
import random
from datetime import datetime
from job_hunter.scout import Scout
from job_hunter.applier import JobApplier
from job_hunter.analysis_crew import JobAnalysisCrew
from job_hunter.mission_state import MissionProgress
from tools.browser_manager import BrowserManager
from tools.logger import logger

class MissionManager:
    def __init__(self, db):
        self.db = db
        self.progress = MissionProgress.load()

    def _start_mission(self, mission_type, total_steps=0):
        self.progress.reset()
        self.progress.update(
            mission_type=mission_type,
            is_active=True,
            total_steps=total_steps,
            status="Starting..."
        )

    def _finish_mission(self, final_status="Complete"):
        self.progress.update(is_active=False, status=final_status)

    def run_live_apply_mission(self, resumes, locations, limit, platforms, status_box):
        """1. Easy Apply Live: Scout + Apply Now"""
        valid_platforms = [p for p in platforms if p in ["LinkedIn", "Xing", "Indeed"]]
        if not valid_platforms:
            status_box.error("❌ None of the selected platforms support Easy Apply Live.")
            return

        total_steps = len(resumes) * len(valid_platforms)
        self._start_mission("Easy Apply Live", total_steps=total_steps)
        p_bar = status_box.progress(0, text="🚀 Live Apply Mission Progress")

        current_step = 0
        for role_name, role_data in resumes.items():
            raw_kw = role_data.get("target_keywords", "")
            keywords = [k.strip() for k in raw_kw.split(';') if k.strip()]
            if not keywords: keywords = [role_name]

            self.db.save_resume_title_history(role_data.get("filename", role_name), keywords)
            locs = [l.strip() for l in locations.split(';') if l.strip()]
            if not locs: locs = ["Germany"]
            resume_path = role_data.get('file_path')

            for p_name in valid_platforms:
                current_step += 1
                perc = min(current_step / total_steps, 1.0)
                p_bar.progress(perc, text=f"🚀 Applying on {p_name} ({current_step}/{total_steps})")
                self.progress.update(current_step=current_step, status=f"Live Applying on {p_name}...")

                for kw in keywords:
                    for loc in locs:
                        msg = f"✨ Applying for **{kw}** in **{loc}** via **{p_name}**..."
                        status_box.info(msg)
                        logger.info(msg)

                        applier = JobApplier(resume_path=resume_path, profile_name="default")
                        try:
                            if p_name == "LinkedIn":
                                res = applier.live_apply_linkedin(kw, loc, target_count=limit, target_role=role_name, callback=lambda m: status_box.info(f"✨ {m}"))
                            elif p_name == "Xing":
                                res = applier.live_apply_xing(kw, loc, target_count=limit, target_role=role_name, callback=lambda m: status_box.info(f"✨ {m}"))
                            elif p_name == "Indeed":
                                res = applier.live_apply_indeed(kw, loc, target_count=limit, target_role=role_name, callback=lambda m: status_box.info(f"✨ {m}"))

                            applied_here = len(res.get('applied', []))
                            self.progress.update(jobs_applied=self.progress.jobs_applied + applied_here)

                        except Exception as e:
                            logger.error(f"Error during Live Apply on {p_name}: {e}")
                        finally:
                            applier.close()

        self.db.archive_applied_jobs()
        self._finish_mission()

    def run_batch_apply_mission(self, eligible_jobs, resume_path, phone_number, status_box):
        """2. Easy Apply Batch: Apply to already scouted jobs"""
        count = len(eligible_jobs)
        self._start_mission("Easy Apply Batch", total_steps=count)
        p_bar = status_box.progress(0, text="🤖 Batch Apply Progress")

        applier = JobApplier(resume_path=resume_path, phone_number=phone_number)

        for i, job in enumerate(eligible_jobs):
            curr = i + 1
            perc = min(curr / count, 1.0)
            p_bar.progress(perc, text=f"🤖 Applying to job {curr} of {count}")
            self.progress.update(current_step=curr, status=f"Applying to {job.get('title')}...")

            url = job.get("link") or job.get("Web Address")
            platform = job.get("platform") or job.get("Platform")
            title = job.get("title") or job.get("Job Title")
            company = job.get("company") or job.get("Company")

            status_box.text(f"🚀 [{i+1}/{count}] Applying to {title} @ {company}...")

            try:
                success, message, is_easy = applier.apply(url, platform, skip_detection=True, job_title=title, company=company)
                if success:
                    self.db.save_applied(f"{title}-{company}", job, {"auto_applied": True})
                    self.progress.update(jobs_applied=self.progress.jobs_applied + 1)
                elif "expired" in message.lower() or "no longer accepting" in message.lower():
                    self.db.park_job(title, company, job)
            except Exception as e:
                logger.error(f"Batch apply error for {title}: {e}")

            time.sleep(random.uniform(2, 5)) # Human jitter

        applier.close()
        self.db.archive_applied_jobs()
        self._finish_mission()

    def run_standard_scrape_mission(self, resumes, locations, limit, platforms, deep_scrape, use_browser_analysis, status_box):
        """3. Launch All Mission: Scout + Deep Scrape + AI Analysis"""
        scout = Scout()
        platforms_arg = platforms if platforms else ["LinkedIn"]

        total_steps = len(resumes) * len(platforms_arg)
        # We'll use 50% for scouting and 50% for analysis if analysis is enabled
        self._start_mission("Scout & Analyze", total_steps=total_steps)
        p_bar = status_box.progress(0, text="🛰️ Mission Progress: Scouting...")

        all_scouted_jobs = []
        current_step = 0

        for role_name, role_data in resumes.items():
            raw_kw = role_data.get("target_keywords", "")
            keywords = [k.strip() for k in raw_kw.split(';') if k.strip()]
            if not keywords: keywords = [role_name]

            self.db.save_resume_title_history(role_data.get("filename", role_name), keywords)

            for kw in keywords:
                for loc in [l.strip() for l in locations.split(';') if l.strip()] or ["Germany"]:
                    current_step += 1
                    # Progress for scouting phase (0-50%)
                    perc = min((current_step / total_steps) * 0.5, 0.5) if use_browser_analysis else min(current_step / total_steps, 1.0)
                    p_bar.progress(perc, text=f"🛰️ Scouting {kw} ({current_step}/{total_steps})")

                    self.progress.update(current_step=current_step, status=f"Scouting {kw} in {loc}...")

                    try:
                        results = scout.launch_mission(
                             keyword=kw,
                             location=loc,
                             limit=limit,
                             platforms=platforms_arg,
                             easy_apply=False,
                             deep_scrape=deep_scrape,
                             status_callback=lambda m: status_box.info(f"🚀 {m}")
                        )
                        for r in results:
                            r['_resume_text'] = role_data.get('text', '')
                            r['_role_name'] = role_name
                        all_scouted_jobs.extend(results)
                        self.progress.update(jobs_scouted=self.progress.jobs_scouted + len(results))
                    except Exception as e:
                        logger.error(f"Scouting failed for {kw}: {e}")

        if all_scouted_jobs and use_browser_analysis:
            self.run_automated_analysis(all_scouted_jobs, status_box, p_bar)
        else:
            p_bar.progress(1.0, text="🛰️ Scouting Complete!")

        self._finish_mission()

    def run_automated_analysis(self, jobs, status_box, p_bar=None):
        unique_jobs = {}
        for job in jobs:
            jid = f"{job.get('title')}-{job.get('company')}"
            if jid not in unique_jobs:
                unique_jobs[jid] = job

        jobs_to_analyze = list(unique_jobs.values())
        total_analyze = len(jobs_to_analyze)

        status_box.info(f"🧠 Starting Automated AI Analysis for {total_analyze} jobs...")
        if p_bar is None:
            p_bar = status_box.progress(0.5, text="🧠 AI Analysis Progress")

        cache = self.db.load_cache()
        analysis_components = ["intel", "cover_letter", "ats", "resume"]

        for i, job in enumerate(jobs_to_analyze):
            jid = f"{job.get('title')}-{job.get('company')}"
            curr = i + 1
            # Progress for analysis phase (50-100%)
            perc = 0.5 + min((curr / total_analyze) * 0.5, 0.5)
            p_bar.progress(perc, text=f"🧠 Analyzing {job.get('title')} ({curr}/{total_analyze})")

            self.progress.update(status=f"Analyzing {job.get('title')}...")

            if jid in cache:
                continue

            scraped_jd = job.get('rich_description') or job.get('description') or ""
            if scraped_jd and len(scraped_jd) > 50:
                context = f"Title: {job.get('title')}\nCompany: {job.get('company')}\nJD: {scraped_jd}"

                try:
                    crew = JobAnalysisCrew(context, job.get('_resume_text', ''), profile_name="default")
                    results = crew.run_analysis(components=analysis_components, use_browser=True)
                    if results and "error" not in results:
                        self.db.save_cache(jid, results)
                except Exception as ae:
                    logger.error(f"Analysis failed for {jid}: {ae}")

            time.sleep(random.uniform(2, 4))

        BrowserManager().close_all_drivers()
