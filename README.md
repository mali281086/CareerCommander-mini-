# 🚀 CareerCommander

**Your AI-Powered Job Hunting Partner.**  
*Scout jobs, analyze requirements, and dominate your applications with autonomous AI agents.*

![Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)

---

## 🌟 Features

-   **🕵️‍♂️ The Scout**: Automatically finds jobs across 5 major platforms (**LinkedIn, Indeed, Stepstone, Xing, ZipRecruiter**) without expensive APIs.
-   **🧠 The Brain**: Plug-and-play AI. Use **Local Ollama (free)** or **Google Gemini (fast)** to power your agents.
-   **📄 Resume Intelligence**: Upload your PDF resume, and the AI will analyze it against every job to give you a specific Match Score and keyword advice.
-   **🤖 Autonomous Agent**: Can "Deep Dive" into specific job links to extract full descriptions and company intel (Mission, Values, Size).

---

## 🛠️ Prerequisites

Before you start, make sure you have:

1.  **Python 3.10+** installed.
2.  **Google Chrome** installed (for the browser agent).
3.  **(Optional) Ollama** installed if you want to run the AI locally for free.
    *   Download from [ollama.com](https://ollama.com)
    *   Run: `ollama run llama3`

---

## 📥 Installation

1.  **Clone/Download this repository**.
2.  **Create a Virtual Environment** (recommended):
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```
3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

---

## ⚙️ Configuration

1.  **Environment Variables**:
    The app will automatically create a `.env` file for you when you save settings in the UI.
    *   **Google Gemini**: Get a free key from [Google AI Studio](https://aistudio.google.com/).
    *   **Ollama**: Works out of the box on `http://localhost:11434`.

---

## 🚀 Usage

Run the application:
```bash
streamlit run app.py
```

### 1️⃣ Step 1: Brain & Resume
*   Select your AI Provider (Local or Google) in the Sidebar.
*   Upload your **PDF Resume**. The AI will scan it and create a "Persona".

### 2️⃣ Step 2: Launch Mission
*   Go to **Mission Control** (Home).
*   Enter your **Role** (e.g., "Data Analyst") and **Location** (e.g., "Germany").
*   Select Platforms (LinkedIn, Stepstone, etc.).
*   Click **🚀 Launch All Missions**.
*   *Note: A browser window will open. Do not minimize it fully, just let it run in the background.*

### 3️⃣ Step 3: Analyze & Apply
*   Go to **Mission Results**.
*   Click on any job to see details.
*   Click **✨ Run AI Analysis** to get a Match Score, Missing Skills list, and Interview Questions.
*   Click **🤖 Agent: Process This Job** to have the bot visit the page and extract deep details.

---

## 🐛 Troubleshooting

*   **"Browser Closed Unexpectedly"**: Ensure you have Chrome installed. If issues persist, try closing all Chrome windows and running again.
*   **"Ollama Connection Error"**: Make sure Ollama is running (`ollama serve` in a separate terminal).
*   **"Xing/LinkedIn Login"**: Some sites require login. Use the **"🛠️ Bot Setup (Login)"** tool in the sidebar to open the browser, log in manually once, and then run your missions.

---

*Designed by TAM Inc.* 🎖️
