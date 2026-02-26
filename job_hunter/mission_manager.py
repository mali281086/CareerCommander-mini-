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
from tools.internet import wait_for_internet, is_internet_available

class MissionManager:
    def __init__(self, db):
        self.db = db
        self.progress = MissionProgress.load()

    def _start_mission(self, mission_type, total_steps=0, config_context=None):
        self.progress.reset()
        self.progress.update(
            mission_type=mission_type,
            is_active=True,
            total_steps=total_steps,
            status="Starting...",
            config_context=config_context or {}
        )

    def _finish_mission(self, final_status="Complete"):
        self.progress.update(is_active=False, status=final_status)

    def run_live_apply_mission(self, resumes, locations, limit, platforms, status_box):
        """1. Easy Apply Live: Scout + Apply Now (Restricted to LinkedIn)"""
        # Platforms selection from UI is already restricted to ["LinkedIn"] for this mode
        valid_platforms = [p for p in platforms if p == "LinkedIn"]
        if not valid_platforms:
            status_box.error("❌ Easy Apply Live is currently restricted to LinkedIn.")
            return

        # Prepare Tasks
        tasks = []
        for role_name, role_data in resumes.items():
            raw_kw = role_data.get("target_keywords", "")
            keywords = [k.strip() for k in raw_kw.split(';') if k.strip()]
            if not keywords: keywords = [role_name]
            locs = [l.strip() for l in locations.split(';') if l.strip()] or ["Germany"]

            for p_name in valid_platforms:
                for kw in keywords:
                    for loc in locs:
                        tasks.append({"label": f"Live Apply for {kw} in {loc} on {p_name}", "completed": False, "type": "live_apply"})

        total_steps = len(tasks)
        self._start_mission("Easy Apply Live", total_steps=total_steps)
        self.progress.update(tasks=tasks)
        p_bar = status_box.progress(0, text="🚀 Live Apply Mission Progress")

        current_step = 0
        task_idx = 0
        for role_name, role_data in resumes.items():
            raw_kw = role_data.get("target_keywords", "")
            keywords = [k.strip() for k in raw_kw.split(';') if k.strip()]
            if not keywords: keywords = [role_name]

            self.db.save_resume_title_history(role_data.get("filename", role_name), keywords)
            locs = [l.strip() for l in locations.split(';') if l.strip()]
            if not locs: locs = ["Germany"]
            resume_path = role_data.get('file_path')

            for p_name in valid_platforms:
                for kw in keywords:
                    for loc in locs:
                        current_step += 1
                        perc = min(current_step / total_steps, 1.0)
                        p_bar.progress(perc, text=f"🚀 Applying for {kw} on {p_name} ({current_step}/{total_steps})")
                        self.progress.update(current_step=current_step, status=f"Live Applying for {kw} on {p_name}...")

                        msg = f"✨ Applying for **{kw}** in **{loc}** via **{p_name}**..."
                        status_box.info(msg)
                        logger.info(msg)

                        applier = JobApplier(resume_path=resume_path, profile_name="default")
                        try:
                            if p_name == "LinkedIn":
                                res = applier.live_apply_linkedin(kw, loc, target_count=limit, target_role=role_name, callback=lambda m: status_box.info(f"✨ {m}"))
                            else:
                                logger.warning(f"Live apply for {p_name} is not supported in this mode.")
                                res = {'applied': []}

                            applied_here = len(res.get('applied', []))
                            # Update task completion
                            self.progress.tasks[task_idx]['completed'] = True
                            self.progress.update(jobs_applied=self.progress.jobs_applied + applied_here)
                            task_idx += 1

                        except Exception as e:
                            logger.error(f"Error during Live Apply on {p_name}: {e}")
                        finally:
                            applier.close()

        self.db.archive_applied_jobs()
        self._finish_mission()

    def run_batch_apply_mission(self, eligible_jobs, resume_path, phone_number, status_box):
        """2. Easy Apply Batch: Apply to already scouted jobs"""
        count = len(eligible_jobs)
        tasks = []
        for job in eligible_jobs:
            title = job.get('title') or job.get('Job Title') or "Unknown Title"
            tasks.append({"label": f"Apply to {title}", "completed": False, "type": "apply"})

        self._start_mission("Easy Apply Batch", total_steps=count)
        self.progress.update(tasks=tasks)
        p_bar = status_box.progress(0, text="🤖 Batch Apply Progress")

        applier = JobApplier(resume_path=resume_path, phone_number=phone_number)

        def get_valid_val(j, *keys):
            for k in keys:
                v = j.get(k)
                # Check for NaN or None or empty
                if v == v and v is not None and str(v).strip() != "" and str(v).lower() != "nan":
                    return v
            return None

        for i, job in enumerate(eligible_jobs):
            curr = i + 1
            perc = min(curr / count, 1.0)
            p_bar.progress(perc, text=f"🤖 Applying to job {curr} of {count}")

            url = get_valid_val(job, "link", "Web Address")
            platform = get_valid_val(job, "platform", "Platform")
            title = get_valid_val(job, "title", "Job Title") or "Unknown Title"
            company = get_valid_val(job, "company", "Company") or "Unknown Company"

            self.progress.update(current_step=curr, status=f"Applying to {title}...")
            status_box.text(f"🚀 [{i+1}/{count}] Applying to {title} @ {company}...")

            if not url or not platform:
                logger.warning(f"Skipping job {title} due to missing URL or Platform.")
                continue

            try:
                success, message, is_easy = applier.apply(url, platform, skip_detection=True, job_title=title, company=company)
                if success:
                    self.db.save_applied(f"{title}-{company}", job, {"auto_applied": True})
                    self.progress.update(jobs_applied=self.progress.jobs_applied + 1)
                elif "expired" in message.lower() or "no longer accepting" in message.lower():
                    self.db.park_job(title, company, job)

                # Mark task as completed
                self.progress.tasks[i]['completed'] = True
                self.progress.save()
            except Exception as e:
                logger.error(f"Batch apply error for {title}: {e}")

            time.sleep(random.uniform(2, 5)) # Human jitter

        applier.close()
        self.db.archive_applied_jobs()
        self._finish_mission()

    def run_standard_scrape_mission(self, resumes, locations, limit, platforms, deep_scrape, use_browser_analysis, status_box):
        """3. Launch All Mission: Scout + Deep Scrape + AI Analysis (Resumable)"""
        platforms_arg = platforms if platforms else ["LinkedIn"]

        # Prepare Backlog and Tasks
        backlog = []
        tasks = []
        for role_name, role_data in resumes.items():
            raw_kw = role_data.get("target_keywords", "")
            keywords = [k.strip() for k in raw_kw.split(';') if k.strip()]
            if not keywords: keywords = [role_name]

            self.db.save_resume_title_history(role_data.get("filename", role_name), keywords)

            for kw in keywords:
                for loc in [l.strip() for l in locations.split(';') if l.strip()] or ["Germany"]:
                    for p in platforms_arg:
                        backlog.append({
                            "keyword": kw, "location": loc, "platform": p,
                            "role_name": role_name, "resume_text": role_data.get('text', ''),
                            "resume_filename": role_data.get("filename", role_name)
                        })
                        tasks.append({"label": f"Scrape for {kw} in {loc} on {p}", "completed": False, "type": "scout"})

        if use_browser_analysis:
            tasks.append({"label": "Run AI Analysis for 0 Jobs", "completed": False, "type": "analyze"})

        total_steps = len(backlog)
        self._start_mission("Scout & Analyze", total_steps=total_steps, config_context={
            "limit": limit, "deep_scrape": deep_scrape, "use_browser_analysis": use_browser_analysis
        })
        self.progress.update(scouting_backlog=backlog, phase="Scouting", tasks=tasks)

        self.resume_mission(status_box)

    def resume_mission(self, status_box):
        """Resumes an incomplete mission from the last saved state."""
        if not self.progress.is_active:
            status_box.error("No active mission to resume.")
            return

        self.progress.update(is_paused=False, status="Resuming...")

        if self.progress.phase == "Scouting":
            self._execute_scouting_loop(status_box)

        # After scouting (or if we started in analysis), run analysis
        if self.progress.is_active and self.progress.phase == "Analysis":
            self._execute_analysis_loop(status_box)

        if self.progress.is_active and not self.progress.scouting_backlog and not self.progress.analysis_backlog:
            self._finish_mission()

    def kill_mission(self):
        """Stops the mission and clears all associated data."""
        self.progress.reset()
        self.db.clear_scouted_jobs()
        BrowserManager().close_all_drivers()

    def _check_interrupts(self, status_box):
        """Checks for internet connection and pause state."""
        # 1. Internet check with 3 retries
        if not is_internet_available():
            resilient = False
            for i in range(3):
                time.sleep(2)
                if is_internet_available():
                    resilient = True
                    break

            if not resilient:
                status_box.warning("📶 Internet disconnected. Pausing mission automatically...")
                self.progress.update(is_paused=True, status="Paused (No Internet)")

        # 2. Pause check
        while self.progress.is_paused:
            status_box.info("⏸️ Mission is paused. Waiting for resume...")
            time.sleep(5)
            self.progress = MissionProgress.load() # Reload state
            if not self.progress.is_active:
                return False # Stop requested

            # Auto-resume check if internet returns
            if self.progress.status == "Paused (No Internet)" and is_internet_available():
                logger.info("Internet restored. Auto-resuming...")
                self.progress.update(is_paused=False, status="Resuming...")
                break

        return True

    def _execute_scouting_loop(self, status_box):
        scout = Scout()
        total_backlog_start = self.progress.total_steps
        use_analysis = self.progress.config_context.get("use_browser_analysis", True)
        limit = self.progress.config_context.get("limit", 15)
        deep_scrape = self.progress.config_context.get("deep_scrape", True)

        p_bar = status_box.progress(0, text="🛰️ Mission Progress: Scouting...")

        while self.progress.scouting_backlog:
            if not self._check_interrupts(status_box): return

            item = self.progress.scouting_backlog[0]
            kw, loc, p_name = item['keyword'], item['location'], item['platform']

            # Calculate progress
            current_idx = total_backlog_start - len(self.progress.scouting_backlog) + 1
            self.progress.update(current_step=current_idx, status=f"Scouting {kw} on {p_name}...")

            perc = min((current_idx / total_backlog_start) * 0.5, 0.5) if use_analysis else min(current_idx / total_backlog_start, 1.0)
            p_bar.progress(perc, text=f"🛰️ Scouting {kw} ({current_idx}/{total_backlog_start})")

            try:
                results = scout.launch_mission(
                     keyword=kw,
                     location=loc,
                     limit=limit,
                     platforms=[p_name],
                     easy_apply=False,
                     deep_scrape=deep_scrape,
                     status_callback=lambda m: status_box.info(f"🚀 {m}")
                )
                for r in results:
                    r['_resume_text'] = item.get('resume_text', '')
                    r['_role_name'] = item.get('role_name', '')

                # Add to analysis backlog
                if use_analysis:
                    self.progress.analysis_backlog.extend(results)

                # Update task status
                task_label = f"Scrape for {kw} in {loc} on {p_name}"
                for task in self.progress.tasks:
                    if task['label'] == task_label and task['type'] == "scout":
                        task['completed'] = True
                        break

                # Update analysis task label
                for task in self.progress.tasks:
                    if task['type'] == "analyze":
                        new_count = len(self.progress.analysis_backlog)
                        task['label'] = f"Run AI Analysis for {new_count} Jobs"
                        break

                self.progress.update(jobs_scouted=self.progress.jobs_scouted + len(results))

                # Pop from backlog and save
                self.progress.scouting_backlog.pop(0)
                self.progress.save()

            except Exception as e:
                logger.error(f"Scouting failed for {kw} on {p_name}: {e}")
                # For platform errors, we could ask user via pending_decision but for now let's just log and skip or retry
                self.progress.update(status=f"Error on {p_name}. Retrying in 30s...")
                time.sleep(30)

        self.progress.update(phase="Analysis")
        p_bar.progress(0.5, text="🛰️ Scouting Complete!")

    def _execute_analysis_loop(self, status_box):
        # Deduplicate backlog
        unique_jobs = {}
        for job in self.progress.analysis_backlog:
            jid = f"{job.get('title')}-{job.get('company')}"
            if jid not in unique_jobs:
                unique_jobs[jid] = job

        jobs_to_analyze = list(unique_jobs.values())
        total_analyze = len(jobs_to_analyze)

        if total_analyze == 0:
            return

        status_box.info(f"🧠 Starting Automated AI Analysis for {total_analyze} jobs...")
        p_bar = status_box.progress(0.5, text="🧠 AI Analysis Progress")

        cache = self.db.load_cache()
        analysis_components = ["intel", "cover_letter", "ats", "resume"]

        while self.progress.analysis_backlog:
            if not self._check_interrupts(status_box): return

            job = self.progress.analysis_backlog[0]
            jid = f"{job.get('title')}-{job.get('company')}"

            # Progress calculation
            # We use a simple count for display
            done_count = total_analyze - len(unique_jobs) + 1 # This is tricky if backlog has duplicates
            # Let's just use the current length of backlog vs total

            curr_step = total_analyze - len(self.progress.analysis_backlog) + 1
            perc = 0.5 + min((curr_step / total_analyze) * 0.5, 0.5)
            p_bar.progress(perc, text=f"🧠 Analyzing {job.get('title')} ({curr_step}/{total_analyze})")
            self.progress.update(status=f"Analyzing {job.get('title')}...")

            if jid not in cache:
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

            # Pop and save
            self.progress.analysis_backlog.pop(0)
            self.progress.save()

        # Mark analysis task as completed
        for task in self.progress.tasks:
            if task['type'] == "analyze":
                task['completed'] = True
                break
        self.progress.save()

        BrowserManager().close_all_drivers()

    def run_automated_analysis(self, jobs, status_box, p_bar=None):
        # Legacy method compatibility - just wrap the new loop
        self.progress.update(analysis_backlog=jobs, phase="Analysis")
        self._execute_analysis_loop(status_box)
