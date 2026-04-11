import sys
import os
sys.path.append(os.path.abspath("."))
from tools.browser_llm import BrowserLLM

try:
    print("Initializing BrowserLLM...")
    llm = BrowserLLM(provider="ChatGPT", headless=False)
    print("Asking ChatGPT...")
    llm._ensure_tab()
    llm.driver.save_screenshot("chatgpt_test_screenshot.png")
    print("Saved screenshot to chatgpt_test_screenshot.png")
    result = llm.ask("Hello, just testing. Reply with 'OK'.", timeout=30)
    print("Result:", result)
    llm.quit()
except Exception as e:
    print("Error:", e)
