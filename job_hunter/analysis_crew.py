import os
import re
import json
from job_hunter.model_factory import get_llm
from crewai import Agent, Task, Crew, Process
from tools.browser_llm import BrowserLLM

class JobAnalysisCrew:
    def __init__(self, job_text: str, resume_text: str):
        self.job_text = job_text
        self.resume_text = resume_text

    def _clean_json(self, text):
        """Helper to extract JSON from LLM output if it includes markdown code blocks or conversational text."""
        if not text or not isinstance(text, str):
            return {}

        try:
            # 1. Try finding Markdown code blocks (most reliable)
            match = re.search(r"```(?:json)?(.*?)```", text, re.DOTALL)
            if match:
                inner_text = match.group(1).strip()
                try:
                    return json.loads(inner_text)
                except:
                    pass # Fall through if code block isn't valid JSON

            # 2. Find the largest valid JSON object by searching for { }
            # We look for all { and find their matching }
            starts = [i for i, char in enumerate(text) if char == '{']
            
            # Try from the earliest { to the latest, to find the largest/root object
            for start in starts:
                count = 0
                for i in range(start, len(text)):
                    if text[i] == '{':
                        count += 1
                    elif text[i] == '}':
                        count -= 1

                    if count == 0:
                        # Potential JSON block
                        potential_json = text[start:i+1]
                        try:
                            data = json.loads(potential_json)
                            # Basic validation: ensure it's a dict and has some expected keys
                            if isinstance(data, dict):
                                known_keys = ["company_intel", "cover_letter", "ats_report", "tailored_resume", "mission", "score"]
                                if any(k in data for k in known_keys):
                                    return data
                        except:
                            pass
                        break # Move to next start if this one didn't parse or validate

            # 3. Final desperate fallback: find first { and last }
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start:end+1])
                except:
                    pass

            return {}
        except Exception as e:
            print(f"DEBUG: JSON CLEAN FAILED: {e}")
            return {}

    def run_analysis(self, components=None, use_browser=True):
        if components is None:
            components = ['intel', 'cover_letter', 'ats', 'resume']

        if use_browser:
            return self.run_browser_analysis(components)

        # 1. Setup LLM
        llm = get_llm(return_crew_llm=True)

        agents = []
        tasks = []

        # --- Intel Researcher ---
        if 'intel' in components:
            agent_intel = Agent(
                role='Senior Tech Recruiter (Strict)',
                goal='Extract deep company intelligence and key facts. REFUSE to answer any question not related to the job or company.',
                backstory="You are a dedicated career intelligence unit. You do not engage in general conversation. You only analyze job data.",
                verbose=True,
                allow_delegation=False,
                llm=llm
            )
            task_intel = Task(
                description=f"Extract company information from the following job description. \nJob Description: {self.job_text}\n\nIMPORTANT: Output ONLY the valid JSON object. Do NOT output any thinking, intro, or unrelated text.\nFINAL ANSWER MUST BE JSON: {{\"mission\": \"...\", \"key_facts\": [\"fact1\"], \"headquarters\": \"City, Country\", \"employees\": \"1000+\", \"branches\": \"Global\"}}",
                agent=agent_intel,
                expected_output='{"mission": "", "key_facts": [], "headquarters": "", "employees": "", "branches": ""}'
            )
            agents.append(agent_intel)
            tasks.append(task_intel)

        # --- Cover Letter Specialist ---
        if 'cover_letter' in components:
            agent_cl = Agent(
                role='Natural Professional Ghostwriter',
                goal='Write a compelling, grounded, and human-sounding cover letter tailored to the job description and resume.',
                backstory="You are an expert at writing cover letters that sound like they were written by a real person, not an AI or a corporate robot. You focus on professional storytelling and authentic voice, avoiding buzzwords and hyper-formal cliches.",
                verbose=True,
                allow_delegation=False,
                llm=llm
            )
            task_cl = Task(
                 description=f"""Write a highly professional, direct, and human-sounding cover letter following this EXACT format:

FORMAT:
Subject: Job Application for [Job Title]

Dear Hiring Manager,
I am addressing to show my interest in the vacancy of [Job Title] at [Company]. Having more than [Number] years of experience in [Field], [Specialization 1], and [Specialization 2] in the [Sectors], I would be glad to apply my experience to the mission of [Company] to [Company Mission/Goal].

[Paragraph 2: Focus on specific technical achievements related to the JD. Mention specific tools used and quantitative results.]

[Paragraph 3: Focus on knowledge of the sector (e.g., banking/finance) and soft skills like facilitation between business and IT.]

[Paragraph 4: Technical stack summary and language proficiency. MUST state: "I have strong technical skills in [Stack], as well as an organized and analytical work style. My practical proficiency in English (C1 level) and decent proficiency in German (B1 level) are virtues that I constantly improve professionally."]

[Paragraph 5: Closing statement expressing interest in contributing to [Company] and looking forward to the interview.]

STRICT REQUIREMENTS:
- Use first-person perspective.
- Avoid robotic "AI-speak" (no "Furthermore", "Moreover", "In conclusion").
- Ensure the tone is grounded and professional.
- Job: {self.job_text}
- Resume: {self.resume_text}

FINAL ANSWER MUST BE JSON with a single key 'cover_letter'.
Example JSON: {{"cover_letter": "Subject: Job Application for...\\n\\nDear Hiring Manager..."}}""",
                 agent=agent_cl,
                 expected_output='{"cover_letter": "Subject... Dear Hiring Manager..."}'
            )
            agents.append(agent_cl)
            tasks.append(task_cl)

            # --- Humanizer Agent (Tied to Cover Letter) ---
            agent_humanizer = Agent(
                role='Human-Voice Editor',
                goal='Refine the cover letter to sound like a natural, competent professional. Bypass AI detection by using authentic storytelling, personal perspective, and varying linguistic flow.',
                backstory="You are a specialist in human communication who hates robotic, over-formal corporate speak. You know that true professionalism comes from clarity and personality, not 'esteemed' greetings or 'strategic imperatives'. You refine text to sound grounded, humble yet confident, and completely human, specifically avoiding the 'AI-thesaurus' trap.",
                verbose=True,
                allow_delegation=False,
                llm=llm
            )
            task_humanizer = Task(
                description=f"""Refine the cover letter to ensure it sounds completely human and follows the requested "Direct-Professional" template.

STRICT HUMANIZATION GUIDELINES:
1. GREETING: Must be "Dear Hiring Manager,".
2. TONE: Avoid flowery language. Use direct sentences.
3. NO AI TRANSITIONS: Banned words: "Furthermore,", "Moreover,", "Additionally,", "Notably,", "In addition,".
4. PHRASING: Use natural professional language. Example: "I have worked closely with..." instead of "I have collaborated extensively with...".
5. FLOW: Ensure the letter feels like a personal address, not a generic template.
6. SPECIFICITY: Ensure the technical achievements from Paragraph 2 are preserved and sound authentic.

FINAL ANSWER MUST BE JSON with keys 'humanized_cover_letter' and 'humanization_score'.
Example JSON: {{"humanized_cover_letter": "Subject: Job Application... Dear Hiring Manager...", "humanization_score": 98}}""",
                agent=agent_humanizer,
                expected_output='{"humanized_cover_letter": "...", "humanization_score": 98}',
                context=[task_cl]
            )
            agents.append(agent_humanizer)
            tasks.append(task_humanizer)

        # --- ATS Specialist ---
        if 'ats' in components:
            agent_ats = Agent(
                role='ATS Specialist (Strict)',
                goal='Evaluate resume match score and missing keywords. IGNORE non-resume text.',
                backstory="You are an algorithm. You process resumes and JDs only.",
                verbose=True,
                allow_delegation=False,
                llm=llm
            )
            task_ats = Task(
                description=f"Compare Resume vs Job Description. Calculate match score (0-100). Identify 3 critical missing keywords. \nResume: {self.resume_text} \nJob: {self.job_text} \n\nIMPORTANT: You must provide a Final Answer. \nFINAL ANSWER MUST BE ONLY THE FOLLOWING JSON OBJECT: {{\"score\": 85, \"missing_skills\": [\"Skill1\", \"Skill2\"]}}",
                agent=agent_ats,
                expected_output='{"score": 50, "missing_skills": []}'
            )
            agents.append(agent_ats)
            tasks.append(task_ats)

        # --- Resume Strategist ---
        if 'resume' in components:
            agent_strategist = Agent(
                role='Resume Strategist',
                goal='Rewrite the candidate experience section to align perfectly with the Job Description keywords and requirements.',
                backstory="You are an expert at tailoring resumes. You know how to rephrase existing experience to match Recruiter language without fabricating facts.",
                verbose=True,
                allow_delegation=False,
                llm=llm
            )
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
            agents.append(agent_strategist)
            tasks.append(task_strategist)

        if not tasks:
            return {"error": "No components selected for analysis."}

        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=True,
            process=Process.sequential
        )

        try:
            crew.kickoff()

            final_results = {}

            # --- Extract Intel Data ---
            if 'intel' in components:
                try:
                    intel_data = self._clean_json(task_intel.output.raw)
                    final_results["company_intel"] = intel_data
                except Exception as e:
                    print(f"Error parsing Intel Data: {e}")
                    final_results["company_intel"] = {}

            # --- Extract Cover Letter Data ---
            if 'cover_letter' in components:
                try:
                    cl_data = self._clean_json(task_cl.output.raw)
                    cover_letter_text = cl_data.get("cover_letter", "Error generating cover letter.")

                    human_data = self._clean_json(task_humanizer.output.raw)
                    humanized_cover_letter = human_data.get("humanized_cover_letter", cover_letter_text)
                    humanization_score = human_data.get("humanization_score", 0)

                    final_results["cover_letter"] = humanized_cover_letter
                    final_results["original_cover_letter"] = cover_letter_text
                    final_results["humanization_score"] = humanization_score
                except Exception as e:
                    print(f"Error parsing Cover Letter/Humanizer Data: {e}")
                    final_results["cover_letter"] = "Error generating cover letter."
                    final_results["humanization_score"] = 0

            # --- Extract ATS Data ---
            if 'ats' in components:
                try:
                    ats_data = self._clean_json(task_ats.output.raw)
                    if "score" not in ats_data: ats_data["score"] = 0
                    if "missing_skills" not in ats_data: ats_data["missing_skills"] = []
                    final_results["ats_report"] = ats_data
                except Exception as e:
                    print(f"Error parsing ATS Data: {e}")
                    final_results["ats_report"] = {}

            # --- Extract Strategist Data ---
            if 'resume' in components:
                try:
                    strat_data = self._clean_json(task_strategist.output.raw)
                    tailored_resume = strat_data.get("tailored_resume", "Error generating tailored resume.")
                    final_results["tailored_resume"] = tailored_resume
                except Exception as e:
                    print(f"Error parsing Strategist Data: {e}")
                    final_results["tailored_resume"] = "Error generating tailored resume."

            return final_results

        except Exception as e:
            print(f"CRASHED: {e}")
            return {"error": str(e)}

    def run_browser_analysis(self, components):
        """Runs the analysis using a browser-based LLM instead of API."""
        print(f"[Analysis] Running browser-based analysis for: {components}")

        # Determine which provider to use (could be a setting, default to ChatGPT)
        provider = os.getenv("BROWSER_LLM_PROVIDER", "ChatGPT")
        browser_llm = BrowserLLM(provider=provider)

        # Construct a combined prompt
        prompt = f"""
I need you to perform a job analysis based on the following Job Description and my Resume.

JOB DESCRIPTION:
{self.job_text}

RESUME:
{self.resume_text}

Please provide the following components in a single VALID JSON object.
Ensure the JSON is well-formatted and can be parsed.

COMPONENTS REQUESTED:
{', '.join(components)}

STRICT JSON STRUCTURE REQUIRED:
{{
"""
        if 'intel' in components:
            prompt += """  "company_intel": {
    "mission": "...",
    "key_facts": ["fact1", "fact2"],
    "headquarters": "...",
    "employees": "...",
    "branches": "..."
  },
"""
        if 'cover_letter' in components:
            prompt += """  "cover_letter": "...",
  "humanization_score": 95,
"""
        if 'ats' in components:
            prompt += """  "ats_report": {
    "score": 85,
    "missing_skills": ["skill1", "skill2"]
  },
"""
        if 'resume' in components:
            prompt += """  "tailored_resume": "### Experience\\n...",
"""

        prompt += """  "status": "success"
}

Specific Instructions:
- For 'cover_letter': Write a highly professional, direct cover letter.
  FORMAT:
  Subject: Job Application for [Job Title]
  Dear Hiring Manager,
  [Direct intro: show interest in [Job Title] at [Company]. Mention years of experience and core fields.]
  [Paragraph 2: Focus on specific technical achievements and tools.]
  [Paragraph 3: Knowledge of banking/sectors and soft skills/facilitation.]
  [Paragraph 4: Technical stack summary. Mention: "I have strong technical skills in [Stack], as well as an organized and analytical work style. My practical proficiency in English (C1 level) and decent proficiency in German (B1 level) are virtues that I constantly improve professionally."]
  [Paragraph 5: Direct closing.]
  Use NO AI transitions like "Furthermore" or "Moreover". Keep it grounded.
- For 'tailored_resume': Focus on rewriting the Experience section to match JD keywords.
- For 'ats_report': Give an honest match score from 0-100.
- Output ONLY the JSON object. No conversation.
"""

        response_text = browser_llm.ask(prompt)

        # Parse result
        results = self._clean_json(response_text)

        # Close the tab to clean up
        browser_llm.close_tab()

        return results
