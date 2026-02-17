import streamlit as st
import time
import random
from datetime import datetime
from job_hunter.scout import Scout
from job_hunter.applier import JobApplier
from job_hunter.analysis_crew import JobAnalysisCrew
from tools.browser_manager import BrowserManager

class MissionManager:
    def __init__(self, db):
        self.db = db

    def run_live_apply_mission(self, resumes, locations, limit, platforms, status_box):
        session_total_applied = 0
        total_skipped = 0
        total_errors = 0
        all_unknown = []

        # Only LinkedIn, Xing, Indeed support Live Apply
        valid_platforms = [p for p in platforms if p in ["LinkedIn", "Xing", "Indeed"]]
        if not valid_platforms:
            status_box.error("❌ None of the selected platforms support Easy Apply Live. (LinkedIn, Xing, Indeed only)")
            return

        total_steps = len(resumes) * len(valid_platforms)
        current_step = 0

        for role_name, role_data in resumes.items():
            raw_kw = role_data.get("target_keywords", "")
            keywords = [k.strip() for k in raw_kw.split(';') if k.strip()]
            if not keywords: keywords = [role_name]

            # Save keywords to history
            self.db.save_resume_title_history(role_data.get("filename", role_name), keywords)

            locs = [l.strip() for l in locations.split(';') if l.strip()]
            if not locs: locs = ["Germany"]

            resume_path = role_data.get('file_path')

            for p_name in valid_platforms:
                current_step += 1
                status_box.info(f"✨ [{current_step}/{total_steps}] Live Applying on **{p_name}**...")

                # We do keywords one by one
                for kw in keywords:
                    for loc in locs:
                        status_box.info(f"✨ [{current_step}/{total_steps}] Applying for **{kw}** in **{loc}** via **{p_name}**...")

                        applier = JobApplier(resume_path=resume_path, profile_name="default")
                        try:
                            if p_name == "LinkedIn":
                                res = applier.live_apply_linkedin(kw, loc, target_count=limit, target_role=role_name, callback=lambda m: status_box.info(f"✨ {m}"))
                            elif p_name == "Xing":
                                res = applier.live_apply_xing(kw, loc, target_count=limit, target_role=role_name, callback=lambda m: status_box.info(f"✨ {m}"))
                            elif p_name == "Indeed":
                                res = applier.live_apply_indeed(kw, loc, target_count=limit, target_role=role_name, callback=lambda m: status_box.info(f"✨ {m}"))

                            applied_here = len(res.get('applied', []))
                            session_total_applied += applied_here
                            total_skipped += len(res.get('skipped', []))
                            total_errors += len(res.get('errors', []))
                            all_unknown.extend(res.get('unknown_questions', []))

                        except Exception as e:
                            status_box.error(f"Error during Live Apply on {p_name}: {e}")
                        finally:
                            applier.close()

        # Cleanup
        if session_total_applied > 0:
            removed = self.db.archive_applied_jobs()
            if removed > 0:
                st.session_state['scouted_jobs'] = self.db.load_scouted()

        status_box.success(f"🎉 Live Apply Complete! Total Applied: {session_total_applied} | Skipped: {total_skipped} | Errors: {total_errors}")

        if all_unknown:
            st.session_state['session_unknown_questions'] = all_unknown

    def run_standard_scrape_mission(self, resumes, locations, limit, platforms, deep_scrape, use_browser_analysis, status_box):
        scout = Scout()
        platforms_arg = platforms if platforms else ["LinkedIn"]

        total = len(resumes)
        all_scouted_jobs = []

        loc_list = [l.strip() for l in locations.split(';') if l.strip()]
        if not loc_list: loc_list = ["Germany"]

        for idx, (role_name, role_data) in enumerate(resumes.items()):
            raw_kw = role_data.get("target_keywords", "")
            keywords = [k.strip() for k in raw_kw.split(';') if k.strip()]
            if not keywords: keywords = [role_name]

            # Save keywords to history
            self.db.save_resume_title_history(role_data.get("filename", role_name), keywords)

            for kw in keywords:
                for loc in loc_list:
                    status_box.info(f"🚀 [{idx+1}/{total}] Scouting & Analyzing for **{kw}** in **{loc}**...")

                    try:
                        results = scout.launch_mission(
                             keyword=kw,
                             location=loc,
                             limit=limit,
                             platforms=platforms_arg,
                             easy_apply=False,
                             deep_scrape=deep_scrape,
                             status_callback=lambda m: status_box.info(f"🚀 [{idx+1}/{total}] {m}")
                        )
                        # Tag results for auto-analysis
                        for r in results:
                            r['_resume_text'] = role_data.get('text', '')
                            r['_role_name'] = role_name
                        all_scouted_jobs.extend(results)
                    except Exception as e:
                        st.error(f"Failed for {kw} in {loc}: {e}")

        # --- AUTOMATED AI ANALYSIS ---
        if all_scouted_jobs:
            self.run_automated_analysis(all_scouted_jobs, use_browser_analysis, status_box)

        status_box.success("🎉 All Missions Complete (Scraped & Analyzed)!")

    def run_automated_analysis(self, jobs, use_browser_analysis, status_box):
        # Deduplicate by Title-Company
        unique_jobs = {}
        for job in jobs:
            jid = f"{job.get('title')}-{job.get('company')}"
            if jid not in unique_jobs:
                unique_jobs[jid] = job

        jobs_to_analyze = list(unique_jobs.values())
        total_analyze = len(jobs_to_analyze)

        status_box.info(f"🧠 Starting Automated AI Analysis for {total_analyze} jobs...")
        prog_bar = st.progress(0)

        # Load existing cache to avoid re-analyzing
        cache = self.db.load_cache()
        analysis_components = ["intel", "cover_letter", "ats", "resume"]

        # Sequential AI Analysis
        for i, job in enumerate(jobs_to_analyze):
            jid = f"{job.get('title')}-{job.get('company')}"

            # Skip if already analyzed
            if jid in cache:
                status_box.info(f"🧠 [{i+1}/{total_analyze}] Already in cache: **{job.get('title')}**")
                prog_bar.progress((i + 1) / total_analyze)
                continue

            scraped_jd = job.get('rich_description') or job.get('description') or ""
            if scraped_jd and len(scraped_jd) > 50:
                context = f"Title: {job.get('title')}\nCompany: {job.get('company')}\nLoc: {job.get('location')}\nLink: {job.get('link','')}\n\nJOB DESCRIPTION:\n{scraped_jd}"

                try:
                    crew = JobAnalysisCrew(context, job.get('_resume_text', ''), profile_name="default")
                    # Force use_browser if Gemini API is removed
                    results = crew.run_analysis(components=analysis_components, use_browser=True)

                    if results and "error" not in results:
                        self.db.save_cache(jid, results)
                        if jid not in st.session_state['job_cache']:
                            st.session_state['job_cache'][jid] = results
                except Exception as ae:
                    st.error(f"Analysis failed for {jid}: {ae}")

            status_box.info(f"🧠 [{i+1}/{total_analyze}] Analysis Complete: **{job.get('title')}**")
            prog_bar.progress((i + 1) / total_analyze)

            # Small delay between analyses
            time.sleep(random.uniform(2, 4))

        # Clean up
        BrowserManager().close_all_drivers()
