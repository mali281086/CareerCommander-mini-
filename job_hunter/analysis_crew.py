import os
import re
import json
from job_hunter.model_factory import get_llm
from crewai import Agent, Task, Crew, Process

class JobAnalysisCrew:
    def __init__(self, job_text: str, resume_text: str):
        self.job_text = job_text
        self.resume_text = resume_text

    def _clean_json(self, text):
        """Helper to extract JSON from LLM output if it includes markdown code blocks or conversational text."""
        try:
            # 1. Try finding Markdown code blocks
            match = re.search(r"```(?:json)?(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()
                return json.loads(text)
            
            # 2. Heuristic: Find JSON by looking for known keys
            # This avoids picking up curly braces in the "Thought" chain
            known_keys = ["mission", "key_facts", "tech_questions", "behavioral_question", "missing_skills", "score", "how_to_ace", "cover_letter", "tailored_resume"]
            best_start = -1
            
            for key in known_keys:
                idx = text.find(f'"{key}"')
                if idx != -1:
                    # found a key, look backwards for the opening brace
                    for i in range(idx, -1, -1):
                        if text[i] == '{':
                            best_start = i
                            break
                    if best_start != -1:
                        break
            
            if best_start != -1:
                # We found the start of the likely real JSON object
                # Now find the matching end
                count = 0
                for i, char in enumerate(text[best_start:], start=best_start):
                    if char == '{': count += 1
                    elif char == '}': count -= 1
                    if count == 0:
                        return json.loads(text[best_start:i+1])
            
            # 3. Fallback to original "find first {" behavior as last resort
            start_obj = text.find('{')
            start_arr = text.find('[')
            
            if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
                 count = 0
                 for i, char in enumerate(text[start_obj:], start=start_obj):
                    if char == '{': count += 1
                    elif char == '}': count -= 1
                    if count == 0:
                        return json.loads(text[start_obj:i+1])

            return {}
        except Exception as e:
            print(f"DEBUG: JSON CLEAN FAILED: {e}")
            print(f"DEBUG: FAIL TEXT: {text}")
            return {}

    def run_analysis(self):
        # 1. Setup LLM
        # Use return_crew_llm=True to get a native crewai.LLM object (fixes OpenAI key errors)
        llm = get_llm(return_crew_llm=True)
        print(f"DEBUG: Using LLM: {type(llm)} with config: {llm.model if hasattr(llm, 'model') else 'Unknown'}")

        # Agent 1: Intel Researcher
        agent_intel = Agent(
            role='Senior Tech Recruiter (Strict)',
            goal='Extract deep company intelligence and key facts. REFUSE to answer any question not related to the job or company.',
            backstory="You are a dedicated career intelligence unit. You do not engage in general conversation. You only analyze job data.",
            verbose=True,
            allow_delegation=False,
            llm=llm
        )

        # Agent 2: Cover Letter Specialist
        agent_cl = Agent(
            role='Professional Career Consultant',
            goal='Write a formal, high-impact cover letter tailored to the job description and user resume.',
            backstory="You are an expert career consultant with 20+ years of experience in executive search. You write sophisticated, professional cover letters that balance enthusiasm with corporate restraint.",
            verbose=True,
            allow_delegation=False,
            llm=llm
        )

        # Agent 3: ATS Specialist
        agent_ats = Agent(
            role='ATS Specialist (Strict)',
            goal='Evaluate resume match score and missing keywords. IGNORE non-resume text.',
            backstory="You are an algorithm. You process resumes and JDs only.",
            verbose=True,
            allow_delegation=False,
            llm=llm
        )

        # Agent 5: Humanizer Agent
        agent_humanizer = Agent(
            role='Senior Executive Editor',
            goal='Refine the cover letter to be 100% professional, formal, and human. Eliminate robotic patterns and over-conversational "AI-humanizing" fillers while maintaining a sophisticated, authoritative tone.',
            backstory="You are an expert editor specializing in professional corporate communication. You understand that in a professional context, especially in regions like Germany, \"humanization\" means clarity, precision, and authentic professional voice—not casual slang or conversational fillers. You excel at varying sentence structure and vocabulary to bypass AI detection while maintaining a formal executive tone.",
            verbose=True,
            allow_delegation=False,
            llm=llm
        )

        # Task 1: Extract Company Intel
        task_intel = Task(
            description=f"Extract company information from the following job description. \nJob Description: {self.job_text}\n\nIMPORTANT: Output ONLY the valid JSON object. Do NOT output any thinking, intro, or unrelated text.\nFINAL ANSWER MUST BE JSON: {{\"mission\": \"...\", \"key_facts\": [\"fact1\"], \"headquarters\": \"City, Country\", \"employees\": \"1000+\", \"branches\": \"Global\"}}",
            agent=agent_intel,
            expected_output='{"mission": "", "key_facts": [], "headquarters": "", "employees": "", "branches": ""}'
        )

        # Task 2: Write Cover Letter
        task_cl = Task(
             description=f"""Write a professional cover letter for this job based on the candidate's resume.
Job: {self.job_text}
Resume: {self.resume_text}

IMPORTANT REQUIREMENTS:
1. HEADER: You MUST extract contact details from the resume and format the header EXACTLY like this:
   [Candidate Name]
   [City, Country]
   Email: [Email]
   Cell: [Phone]
   LinkedIn: [Link]
   Github: [Link (if found)]

2. SUBJECT LINE: Must be exactly "Application for [Job Title] (m/f/d)"

3. LANGUAGE:
   - Write strictly in ENGLISH.
   - You MUST explicitly state: "I possess strong communication skills, with English proficiency at C1 level, and German language skills at B1 level. I am actively learning German to further integrate into the team and better understand the local context and company culture."

4. BODY:
   - Professional, enthusiastic intro.
   - Highlight key matching experience metrics.
   - Mention motivation for the specific company.

FINAL ANSWER MUST BE JSON with a single key 'cover_letter'.
Example JSON: {{"cover_letter": "Sheikh Ali Mateen\\nBerlin, Germany\\n..."}}""",
             agent=agent_cl,
             expected_output='{"cover_letter": "Header... Body..."}'
        )

        # Task 3: ATS (Use FULL context)
        task_ats = Task(
            description=f"Compare Resume vs Job Description. Calculate match score (0-100). Identify 3 critical missing keywords. \nResume: {self.resume_text} \nJob: {self.job_text} \n\nIMPORTANT: You must provide a Final Answer. \nFINAL ANSWER MUST BE ONLY THE FOLLOWING JSON OBJECT: {{\"score\": 85, \"missing_skills\": [\"Skill1\", \"Skill2\"]}}",
            agent=agent_ats,
            expected_output='{"score": 50, "missing_skills": []}'
        )

        # Agent 4: Resume Strategist
        agent_strategist = Agent(
            role='Resume Strategist',
            goal='Rewrite the candidate experience section to align perfectly with the Job Description keywords and requirements.',
            backstory="You are an expert at tailoring resumes. You know how to rephrase existing experience to match Recruiter language without fabricating facts.",
            verbose=True,
            allow_delegation=False,
            llm=llm
        )

        # Task 4: Strategize Resume
        task_strategist = Task(
            description=f"""Rewrite the 'Experience' section of the resume to resonate with the Job Description. 
            Highlight relevant skills and achievements that match the JD. 
            Do NOT invent new experience, but reframe existing one.
            JD: {self.job_text}
            Resume: {self.resume_text}
            
            FINAL ANSWER MUST BE JSON with a single key 'tailored_resume'.
            Example JSON: {{"tailored_resume": "### Professional Experience ... "}}""",
            agent=agent_strategist,
            expected_output='{"tailored_resume": "Markdown text..."}'
        )

        # Task 5: Humanize Cover Letter
        task_humanizer = Task(
            description=f"""Review and refine the cover letter to achieve maximum human authenticity and professional impact.

STRICT GUIDELINES:
1. FORMAL TONE: This is for a professional job application in Germany. DO NOT use casual language, slang, or conversational fillers.
2. FORBIDDEN PHRASES: Avoid "Honestly,", "Pretty neat,", "I've got,", "diving deep,", "Honestly," or any phrase that sounds like a bot trying to be "friendly."
3. RESTRAINED CONFIDENCE: Replace enthusiastic but vague phrases (e.g., "really strong match", "really contribute") with assertive, neutral, and fact-based professional language (e.g., "my qualifications align closely with the requirements", "I am well-positioned to contribute").
4. SHARPNESS: Tighten the text. Remove repetitive mentions of "data analysis" or "dashboards." Make every sentence count.
5. BYPASS AI DETECTION: Use varied sentence lengths (burstiness) and sophisticated vocabulary (perplexity). Avoid common AI transition words like "Moreover," "Furthermore," or "In conclusion." Use more natural, direct transitions.

FINAL ANSWER MUST BE JSON with keys 'humanized_cover_letter' and 'humanization_score'.
The humanization_score (0-100) should reflect how much the letter avoids robotic patterns and conversational AI tropes while remaining 100% formal and professional.
Example JSON: {{"humanized_cover_letter": "Dear Mr. Schmidt...", "humanization_score": 98}}""",
            agent=agent_humanizer,
            expected_output='{"humanized_cover_letter": "...", "humanization_score": 95}',
            context=[task_cl]
        )

        crew = Crew(
            agents=[agent_intel, agent_cl, agent_ats, agent_strategist, agent_humanizer],
            tasks=[task_intel, task_cl, task_ats, task_strategist, task_humanizer],
            verbose=True,
            process=Process.sequential
        )

        try:
            results = crew.kickoff()
            # --- Intel Data ---
            try:
                print(f"DEBUG: INTEL RAW: {task_intel.output.raw}")
                intel_data = self._clean_json(task_intel.output.raw)
            except Exception as e:
                print(f"Error parsing Intel Data: {e}")
                intel_data = {}

            # --- Cover Letter Data ---
            try:
                print(f"DEBUG: CL RAW: {task_cl.output.raw}")
                cl_data = self._clean_json(task_cl.output.raw)
                cover_letter_text = cl_data.get("cover_letter", "Error generating cover letter.")
            except Exception as e:
                print(f"Error parsing Cover Letter Data: {e}")
                cover_letter_text = "Error generating cover letter."

            # --- ATS Data ---
            try:
                print(f"DEBUG: ATS RAW: {task_ats.output.raw}")
                ats_data = self._clean_json(task_ats.output.raw)
                if "score" not in ats_data: ats_data["score"] = 0
                if "missing_skills" not in ats_data: ats_data["missing_skills"] = []
            except Exception as e:
                print(f"Error parsing ATS Data: {e}")
                ats_data = {}

            try:
                print(f"DEBUG: STRAT RAW: {task_strategist.output.raw}")
                strat_data = self._clean_json(task_strategist.output.raw)
                tailored_resume = strat_data.get("tailored_resume", "Error generating tailored resume.")
            except Exception as e:
                print(f"Error parsing Strategist Data: {e}")
                tailored_resume = "Error generating tailored resume."

            # --- Humanizer Data ---
            try:
                print(f"DEBUG: HUMAN RAW: {task_humanizer.output.raw}")
                human_data = self._clean_json(task_humanizer.output.raw)
                humanized_cover_letter = human_data.get("humanized_cover_letter", cover_letter_text)
                humanization_score = human_data.get("humanization_score", 0)
            except Exception as e:
                print(f"Error parsing Humanizer Data: {e}")
                humanized_cover_letter = cover_letter_text
                humanization_score = 0

            return {
                "company_intel": intel_data,
                "cover_letter": humanized_cover_letter,
                "original_cover_letter": cover_letter_text,
                "humanization_score": humanization_score,
                "ats_report": ats_data,
                "tailored_resume": tailored_resume
            }

        except Exception as e:
            print(f"CRASHED: {e}")
            return {
                "company_intel": {},
                "cover_letter": "Analysis failed.",
                "ats_report": {},
                "tailored_resume": "Analysis failed."
            }
