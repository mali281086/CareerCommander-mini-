import streamlit as st

def render_settings_view(db):
    st.title("⚙️ Bot Settings")
    st.caption("Configure auto-answers for LinkedIn Easy Apply questions. Unknown questions are logged here.")

    bot_config = db.load_bot_config()
    answers = bot_config.get("answers", {})
    unknown = bot_config.get("unknown_questions", [])

    # Stats
    c1, c2 = st.columns(2)
    c1.metric("📝 Configured Answers", len(answers))
    c2.metric("❓ Unknown Questions", len(unknown))

    st.divider()

    tab_answers, tab_unknown, tab_add, tab_behavior, tab_profile, tab_blacklist, tab_selectors, tab_test = st.tabs([
        "📝 My Answers",
        "❓ Unknown Questions",
        "➕ Add New",
        "🤖 Bot Behavior",
        "👤 User Profile",
        "🚫 Blacklist",
        "🛠️ Advanced Selectors",
        "🧪 Test Mode"
    ])

    with tab_answers:
        st.subheader("Current Question-Answer Mappings")

        if answers:
            # Search within answers
            search_ans = st.text_input("🔍 Search answers...", key="search_answers", placeholder="Type to filter...")

            filtered_answers = {k: v for k, v in answers.items() if search_ans.lower() in k.lower() or search_ans.lower() in v.lower()} if search_ans else answers

            st.caption(f"Showing {len(filtered_answers)} of {len(answers)} answers")

            for i, (question, answer) in enumerate(list(filtered_answers.items())):
                with st.container():
                    c_q, c_a, c_del = st.columns([3, 2, 1])
                    c_q.markdown(f"**{question}**")
                    new_ans = c_a.text_input("Answer", value=answer, key=f"ans_pg_{i}", label_visibility="collapsed")

                    if new_ans != answer:
                        db.add_answer(question, new_ans)
                        st.toast(f"Updated: '{question}' → '{new_ans}'")
                        st.rerun()

                    if c_del.button("🗑️", key=f"del_pg_{i}", help="Delete this answer"):
                        db.delete_answer(question)
                        st.toast(f"Deleted: '{question}'")
                        st.rerun()
        else:
            st.info("No answers configured yet. Add some in the 'Add New' tab!")

    with tab_unknown:
        st.subheader("Unknown Questions Encountered")

        if unknown:
            st.warning(f"**{len(unknown)} question(s)** the bot couldn't answer. Add your answers below!")

            for j, uq in enumerate(unknown):
                q_text = uq.get("question", "")
                job_info = f"{uq.get('job_title', '')} @ {uq.get('company', '')}" if uq.get('job_title') else ""
                timestamp = uq.get("timestamp", "")

                with st.container():
                    st.markdown(f"### {j+1}. {q_text}")
                    if job_info:
                        st.caption(f"📍 From: {job_info}")
                    if timestamp:
                        st.caption(f"🕐 {timestamp[:10]}")

                    c_input, c_save = st.columns([4, 1])
                    new_answer = c_input.text_input("Your Answer", key=f"uq_pg_{j}", placeholder="Enter your answer for this question...")

                    if c_save.button("💾 Save", key=f"uq_save_pg_{j}", type="primary"):
                        if new_answer:
                            db.add_answer(q_text, new_answer)
                            st.toast(f"✅ Added answer for '{q_text}'")
                            st.rerun()
                        else:
                            st.error("Please enter an answer")

                    st.divider()

            if st.button("🧹 Clear All Unknown Questions", type="secondary"):
                db.clear_unknown_questions()
                st.toast("Cleared all unknown questions")
                st.rerun()
        else:
            st.success("✅ No unknown questions! The bot has answers for all encountered questions.")

    with tab_add:
        st.subheader("Add New Question-Answer Mapping")

        c_q, c_a = st.columns([3, 2])
        new_q = c_q.text_input("Question Pattern", placeholder="e.g. 'years of experience'", key="add_q_pg")
        new_a = c_a.text_input("Answer", placeholder="e.g. '5'", key="add_a_pg")

        if st.button("➕ Add Answer", type="primary"):
            if new_q and new_a:
                db.add_answer(new_q, new_a)
                st.toast(f"✅ Added: '{new_q}' → '{new_a}'")
                st.rerun()
            else:
                st.error("Please enter both question pattern and answer")

    with tab_behavior:
        st.subheader("🤖 Bot Behavior Settings")

        if "settings" not in bot_config:
            bot_config["settings"] = {}

        # Headless AI Toggle
        current_headless = bot_config.get("settings", {}).get("ai_headless", True)
        new_headless = st.toggle("Headless AI Analysis", value=current_headless,
                                 help="If enabled, AI analysis happens in the background. Disable to see the AI browser (useful for logging in or debugging).")

        if new_headless != current_headless:
            bot_config["settings"]["ai_headless"] = new_headless
            db.save_bot_config(bot_config)
            st.toast("✅ Bot Behavior Updated!")
            st.rerun()
            
        st.divider()
        
        # Cover Letter Path Setting
        st.subheader("📄 Document Export Settings")
        default_path = r"Cover_Letter.pdf"
        current_path = bot_config.get("settings", {}).get("cover_letter_path", default_path)
        new_path = st.text_input("Cover Letter Save Path", value=current_path, 
                                 placeholder=r"e.g. D:\Documents\MyJobs\Cover_Letter.pdf",
                                 help="Where the PDF cover letter will be saved. Ensure the folder exists and use .pdf extension.")
        
        if new_path != current_path:
            bot_config["settings"]["cover_letter_path"] = new_path
            db.save_bot_config(bot_config)
            st.toast("✅ Export Path Updated!")
            st.rerun()

        st.divider()
        st.caption("Note: These settings affect how the AI Analysis and Auto-Apply engines interact with your browser.")

    with tab_profile:
        st.subheader("👤 User Profile (For Cover Letters)")
        st.caption("This information is embedded directly into your generated Cover Letter PDFs.")

        if "profile" not in bot_config:
            bot_config["profile"] = {
                "name": "",
                "address": "",
                "email": "",
                "cell": "",
                "linkedin": "",
                "github": ""
            }

        prof = bot_config["profile"]
        c_p1, c_p2 = st.columns(2)
        new_name = c_p1.text_input("Full Name", value=prof.get("name", ""))
        new_address = c_p2.text_input("Address", value=prof.get("address", ""))
        
        c_p3, c_p4 = st.columns(2)
        new_email = c_p3.text_input("Email", value=prof.get("email", ""))
        new_cell = c_p4.text_input("Phone / Cell", value=prof.get("cell", ""))
        
        c_p5, c_p6 = st.columns(2)
        new_linkedin = c_p5.text_input("LinkedIn URL", value=prof.get("linkedin", ""))
        new_github = c_p6.text_input("GitHub URL", value=prof.get("github", ""))

        if st.button("💾 Save Profile", type="primary", use_container_width=True):
            bot_config["profile"] = {
                "name": new_name,
                "address": new_address,
                "email": new_email,
                "cell": new_cell,
                "linkedin": new_linkedin,
                "github": new_github
            }
            db.save_bot_config(bot_config)
            st.success("✅ Profile Saved!")
            st.rerun()

    with tab_blacklist:
        st.subheader("🚫 Global Blacklist")
        st.caption("Jobs matching these keywords will be automatically dropped during scouting.")
        
        blacklist = db.load_blacklist()
        
        c1, c2 = st.columns(2)
        
        # Titles
        bl_titles = c1.text_area("🚫 Blocked Job Titles (one per line)", 
                                 value="\n".join(blacklist.get("titles", [])),
                                 help="e.g. 'Intern', 'Working Student', 'Senior'")
        
        # Companies
        bl_companies = c2.text_area("🚫 Blocked Companies (one per line)", 
                                   value="\n".join(blacklist.get("companies", [])),
                                   help="e.g. 'Amazon', 'Facebook'")
        
        # Safe Phrases
        st.subheader("✅ Safe Phrases (Rescue Mission)")
        st.caption("If a title is blocked but contains a safe phrase, it will be kept. (e.g. Block 'Senior', but keep 'Senior Data Analyst')")
        safe_phrases = st.text_area("Safe Phrases (one per line)", 
                                   value="\n".join(blacklist.get("safe_phrases", [])),
                                   help="Keywords that 'rescue' a job from the blacklist.")
        
        if st.button("💾 Save Blacklist", type="primary"):
            new_titles = [t.strip() for t in bl_titles.split("\n") if t.strip()]
            new_companies = [c.strip() for c in bl_companies.split("\n") if c.strip()]
            new_safe = [s.strip() for s in safe_phrases.split("\n") if s.strip()]
            
            db.save_blacklist(new_companies, new_titles, new_safe)
            st.success("✅ Blacklist Updated!")
            st.rerun()

    with tab_selectors:
        st.subheader("🛠️ CSS/XPath Selectors Configuration")
        st.caption("Customize the selectors used by the bot to interact with job boards. Only modify if you know what you are doing!")

        selectors_dict = db.load_selectors()
        import yaml

        selectors_yaml = yaml.dump(selectors_dict, default_flow_style=False)

        # YAML Editor
        new_selectors_yaml = st.text_area("Selectors (YAML Format)", value=selectors_yaml, height=500)

        if st.button("💾 Save Selectors", type="primary"):
            try:
                new_selectors_dict = yaml.safe_load(new_selectors_yaml)
                db.save_selectors(new_selectors_dict)
                st.success("✅ Selectors updated successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to save selectors: {e}")

    with tab_test:
        st.subheader("🧪 Single-Link Test Mode")
        st.caption("Run a full scrape and AI analysis mission on a single URL. Data is saved temporarily for troubleshooting.")

        c_t1, c_t2 = st.columns(2)
        test_platform = c_t1.selectbox("Platform", ["LinkedIn", "Xing", "Indeed", "Stepstone", "ZipRecruiter"])
        
        resumes = st.session_state.get('resumes', {})
        resume_options = list(resumes.keys())
        test_resume = c_t2.selectbox("Resume Context", resume_options) if resume_options else None
        
        c_t3, c_t4 = st.columns(2)
        test_title = c_t3.text_input("Job Title (for AI Context)", "Test Job Title")
        test_company = c_t4.text_input("Company (for AI Context)", "Test Company")
        
        test_link = st.text_input("Job Link URL", placeholder="https://www.linkedin.com/jobs/view/...")
        
        if st.button("🚀 Run Test Mission", type="primary", use_container_width=True):
            if not test_link:
                st.error("Please provide a job link.")
            elif not test_resume:
                st.error("Please configure at least one resume in Settings.")
            else:
                from job_hunter.scout import Scout
                from job_hunter.analysis_crew import JobAnalysisCrew
                import json
                from pathlib import Path
                
                scout = Scout()
                if test_platform not in scout.scrapers:
                    st.error(f"Scraper for {test_platform} not initialized.")
                else:
                    status_box = st.empty()
                    
                    try:
                        # 1. Scrape
                        status_box.info(f"🕵️ Scraping details from {test_platform}...")
                        scraper = scout.scrapers[test_platform]
                        details = scraper.fetch_details(test_link)
                        
                        if not details or not details.get('description'):
                            status_box.error("❌ Failed to extract description from the provided link.")
                        else:
                            # 2. AI Analysis
                            status_box.info("🧠 Running AI Analysis...")
                            desc = details.get('description')
                            context = f"Title: {test_title}\nCompany: {test_company}\nJD: {desc}"
                            resume_text = resumes[test_resume].get('text', '')
                            
                            crew = JobAnalysisCrew(context, resume_text, profile_name="default")
                            # Fetch components from session state like mission manager does
                            components = ["ats_report", "humanization_score", "company_intel", "cover_letter"]
                            analysis_results = crew.run_analysis(components=components, use_browser=True)
                            
                            # 3. Save & Show
                            output_data = {
                                "title": test_title,
                                "company": test_company,
                                "link": test_link,
                                "platform": test_platform,
                                "scraped_details": details,
                                "ai_analysis": analysis_results
                            }
                            
                            test_file = Path("data/test_job_data.json")
                            test_file.parent.mkdir(exist_ok=True)
                            with open(test_file, 'w', encoding='utf-8') as f:
                                json.dump(output_data, f, indent=2, ensure_ascii=False)
                                
                            status_box.success("✅ Test Mission Complete! Results saved to `data/test_job_data.json`")
                            
                            with st.expander("Show Test Results", expanded=True):
                                st.json(output_data)
                                
                    except Exception as e:
                        status_box.error(f"❌ Test failed: {e}")
                    finally:
                        from tools.browser_manager import BrowserManager
                        BrowserManager().close_all_drivers()
