# 🎖️ CareerCommander (Mini)

> **An AI-powered, multi-platform job hunting automation suite built with Python, Streamlit, Selenium, and Google Gemini.**

---

## 🧠 What Is It?

CareerCommander is a **personal job search command center** that automates the entire lifecycle of job hunting — from **discovering jobs** across multiple platforms, to **analyzing them with AI**, to **auto-applying** with one click. It is designed for the German/EU job market but supports English roles as well.

---

## 🗺️ Application Flow (End-to-End)

```
Upload Resume(s)  →  Set Target Roles & Keywords  →  Launch Missions
       ↓                                                     ↓
  AI parses text                              ┌──────────────┴──────────────┐
                                              │                             │
                                     Easy Apply Live               Standard Scrape
                                    (Scout + Apply)              (Scout + Deep Scrape)
                                              │                             │
                                   Applies immediately              Saves to "Scouted"
                                              │                             │
                                              ↓                             ↓
                                       Applied Jobs              AI Analysis (Browser-based)
                                                                   ↓       ↓       ↓
                                                               Intel  Cover  ATS Match
                                                              Letter  Resume  Score
                                                                            ↓
                                                                   Easy Apply Batch
                                                                            ↓
                                                                     Applied Jobs
```

---

## 📱 Views / Pages

### 1. 🏠 **Home** — Command Center
- **Multi-Resume Upload** (PDF) — supports multiple resumes for different roles
- **Target Job Titles / Keywords** — semicolon-separated, per resume (e.g. `Data Analyst; Business Analyst`)
- **Target Locations** — semicolon-separated (e.g. `Germany; Berlin; Remote`)
- **Platform Selection** — LinkedIn, Indeed, Xing, Stepstone, ZipRecruiter
- **Scrape Limit** — max jobs per keyword per platform
- **Mode Toggle:**
  - **✨ Easy Apply Live** — Scout + Apply immediately (no AI), for LinkedIn, Xing, Indeed only
  - **🔍 Deep Scrape** — Full scraping with detailed JD fetch + AI analysis later
- **🚀 Launch All Missions** — starts the selected workflow

### 2. 📋 **Explorer** — Scouted Jobs Dashboard
- **Interactive Data Table** with columns: Title, Company, Platform, Language, Easy Apply, Status
- **Inline Actions:**
  - ✅ Mark as Applied
  - 🗑️ Delete
  - 🅿️ Park (hide/ignore)
  - 🔗 Direct Apply Link
- **Filtering** by Platform, Target Role, Language, Easy Apply status
- **Bulk Actions** — Delete or Park all jobs of a specific language
- **🏁 End Day / Archive Applied** — removes applied jobs from active view
- **🤖 Easy Apply Batch** — auto-applies to all eligible Easy Apply jobs in the list
- **AI Analysis Panel** (per selected job):
  - 🏢 Company Deep Intel (mission, HQ, employees, key facts)
  - 📝 AI-Generated Cover Letter (with humanization score)
  - 🎯 ATS Match Score (with missing skills breakdown)
  - 📄 Strategized/Tailored Resume
  - 💬 AI Interview Chat (ask questions about the job)
- **📈 Metrics Dashboard** — charts, applied/day average, platform breakdown

### 3. 📬 **Applied Jobs** — Application History
- **Full history** of all applied jobs with timestamps
- **AI analysis results** attached to each application
- **Status tracking** per job
- **Delete** individual applications

### 4. 🤝 **Networking** — LinkedIn Outreach
- **Automated LinkedIn messaging** to 1st-degree connections in a target region
- **Customizable message template** with `{first_name}` placeholder
- **Max contacts limit** to control outreach volume

### 5. ⚙️ **Bot Settings**
- **Question & Answer Config** — pre-set answers for common application form fields
  - Years of experience, visa sponsorship, relocation, education, languages, etc.
- **Unknown Questions Log** — captures questions the bot couldn't answer during auto-apply
- **Add/Edit/Delete** answer mappings
- **Intelligent Matching** — fuzzy keyword-based matching for form questions

---

## 🔧 Core Modules

### Scrapers (`job_hunter/scrapers/`)
| Scraper | Platform | Easy Apply Detection |
|---------|----------|---------------------|
| `linkedin.py` | LinkedIn | ✅ Badge-based |
| `indeed.py` | Indeed (de.indeed.com) | ✅ "Einfach bewerben" / badge |
| `xing.py` | Xing | ✅ "Schnellbewerbung" |
| `stepstone.py` | Stepstone | ❌ Standard only |
| `ziprecruiter.py` | ZipRecruiter | ❌ Standard only |

### Scout (`job_hunter/scout.py`)
- Orchestrates multi-platform job searching
- Calls individual scrapers sequentially
- Optional **Deep Scrape** — fetches full JD + language detection via integrated scraper methods
- Filters out already-applied, parked, and blacklisted jobs automatically
- Saves results to `scouted_jobs.json`

### Applier (`job_hunter/applier.py`)
- **Platform-specific apply logic:**
  - **LinkedIn:** Modal-based Easy Apply (handles multi-step forms, iframes, file uploads)
  - **Xing:** Schnellbewerbung form automation
  - **Indeed:** Easy Apply iframe automation
- **Smart Form Filling:** uses bot_config Q&A mappings
- **Resume Upload:** auto-attaches selected PDF
- **Already Applied Detection:** checks page text for "beworben", "applied", etc.
- **Expired Job Detection:** detects "no longer accepting", "abgelaufen", etc.
- **Unknown Question Logging:** captures unanswered fields for later configuration

### AI Analysis (`job_hunter/analysis_crew.py`)
- **Powered by Browser-based LLM** (ChatGPT/Gemini/Copilot via Selenium)
- **Unified Analysis:**
  - 🕵️ Company Intel — researches the company
  - 📝 Cover Letter — generates humanized cover letter
  - 🎯 ATS Match — scores resume vs JD match
  - 📄 Resume Strategist — tailors experience bullets

### Data Manager (`job_hunter/data_manager.py`)
- **JSON-based persistence** (no database required):
  - `scouted_jobs.json` — active job pipeline (list)
  - `applied_jobs.json` — application history (dict, keyed by Job Title-Company)
  - `parked_jobs.json` — hidden/ignored jobs
  - `analysis_cache.json` — cached AI results
  - `bot_config.json` — Q&A mappings + unknown questions
  - `blacklist.json` — blocked companies, titles, safe phrases
  - `resume_config.json` — resume metadata and target keywords
  - `resume_title_history.json` — previously used job titles per resume

### Career Auditor (`job_hunter/career_auditor.py`)
- AI-powered **career audit report** based on application history
- Generates strategic recommendations in Markdown

---

## ⚡ Key Workflows

### Easy Apply Live
```
For each Platform (LinkedIn → Xing → Indeed):
    For each Keyword (from all resumes):
        1. Scout: Find Easy Apply jobs (no deep scrape)
        2. Apply: Immediately apply to each found job
        3. Save: Move to Applied Jobs
        4. Cleanup: Archive from Scouted list
```
- **No AI Analysis** — speed-optimized for volume
- **Fresh browser session per platform** — avoids session conflicts

### Easy Apply Batch
```
1. User reviews Scouted Jobs in Explorer
2. (Optional) Run AI Analysis on individual jobs
3. Click "Easy Apply Batch" button
4. Bot applies to ALL eligible Easy Apply jobs sequentially
5. Results logged, expired jobs auto-parked
```

### Standard Deep Scrape
```
1. Scout finds jobs across selected platforms
2. ContentFetcher visits each job URL for full JD
3. Language detection applied
4. Jobs saved to Scouted pipeline
5. User reviews in Explorer, runs AI Analysis per job
```

---

## 🛡️ Safety Features

- **Blacklist System** — block companies or job title keywords (with "safe phrases" rescue)
- **Duplicate Prevention** — skips already-applied and parked jobs during scouting
- **Expired Job Parking** — auto-detects and parks expired postings
- **Resume Path Validation** — absolute path enforcement for file uploads
- **Session State Management** — Streamlit session isolation for concurrent safety

---

## 🗂️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Streamlit |
| **Browser Automation** | Selenium + ChromeDriver |
| **AI / LLM** | Browser-based AI (ChatGPT/Gemini via Selenium) |
| **Data Storage** | JSON files (no database) |
| **Language Detection** | `langdetect` |
| **Resume Parsing** | PyPDF / custom parser |
| **Environment** | Python 3.13, Windows |

---

## 📁 Project Structure

```
CareerCommander(Mini)/
├── app.py                    # Main Streamlit application (2200+ lines)
├── requirements.txt          # Python dependencies
├── .env                      # API keys and browser config
├── data/                     # All persistent JSON data
│   ├── scouted_jobs.json
│   ├── applied_jobs.json
│   ├── parked_jobs.json
│   ├── analysis_cache.json
│   ├── bot_config.json
│   ├── blacklist.json
│   ├── resume_config.json
│   └── resumes/              # Uploaded PDF resumes
├── job_hunter/               # Core engine
│   ├── scout.py              # Multi-platform job search orchestrator
│   ├── applier.py            # Auto-apply engine (LinkedIn, Xing, Indeed)
│   ├── analysis_crew.py      # Browser-based AI analysis
│   ├── career_auditor.py     # Career audit report generator
│   ├── career_advisor.py     # AI career advisor
│   ├── data_manager.py       # JSON data persistence layer
│   ├── resume_parser.py      # PDF resume text extraction
│   └── scrapers/             # Platform-specific scrapers
│       ├── base_scraper.py
│       ├── linkedin.py
│       ├── indeed.py
│       ├── xing.py
│       ├── stepstone.py
│       ├── ziprecruiter.py
│       └── linkedin_outreach.py
└── tools/
    └── browser_manager.py    # Chrome browser lifecycle management
```
