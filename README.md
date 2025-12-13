# 🎖️ CareerCommander

**Take command of your career with AI.**

CareerCommander is your **Autonomous Career Operations Platform**. It transforms the chaotic, manual process of job hunting into a strategic, data-driven military operation.

We don't just "find jobs"—we mobilize a squad of AI agents to **Scout**, **Analyze**, and **Prepare** you for victory in the job market.

## 🚀 Mission Capabilities

### Phase 1: Reconnaissance (Data Aggregation)
*   **Multi-Front Scraping**: Simultaneously gathers intelligence from **Indeed**, **Xing**, **Stepstone**, and **ZipRecruiter**.
*   **Stealth Operations**: Built-in anti-bot handling ensures your scouts get the data without being detected.
*   **Unified Command Center**: A single Dashboard to view, filter, and deduplicate all incoming job alerts.
*   **Local Persistence**: All intelligence is saved locally (JSON), ensuring you never lose a lead.

### Phase 2: Intelligence & Strategy (Coming Soon with CrewAI)
*   **🕵️ The Investigator**: Auto-generates deep-dive dossiers on target companies (Funding, Culture, News).
*   **🧠 The Strategist**: Analyzes JD vs. Resume gaps and generates tailored talking points.
*   **⚔️ The Drill Sergeant**: Conducts mock interviews with role-specific questions derived from the company's tech stack.

## 🛠️ The Armory (Tech Stack)

*   **Frontend**: [Streamlit](https://streamlit.io/)
*   **Scraping**: [Playwright](https://playwright.dev/python/)
*   **Intelligence**: [CrewAI](https://www.crewai.com/) (Integration in progress)
*   **Data**: [Pandas](https://pandas.pydata.org/)

## 📦 Mobilization (Installation)

1.  **Clone the Base**
    ```bash
    git clone https://github.com/yourusername/career-commander.git
    cd career-commander
    ```

2.  **Equip Gear (Virtual Env)**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # Windows
    source venv/bin/activate # Mac/Linux
    ```

3.  **Load Amenities**
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

4.  **Launch Operations**
    ```bash
    streamlit run app.py
    ```

## ⚠️ Engagement Rules (Disclaimer)

This tool is for educational purposes only. Automated scraping calls for responsible usage. Respect `robots.txt` and platform Terms of Service.

---
*Built with ❤️ by your AI Pair Programmer*
