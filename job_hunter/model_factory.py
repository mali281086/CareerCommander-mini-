import os
from langchain_google_genai import ChatGoogleGenerativeAI
from crewai import LLM

def get_llm(return_crew_llm=False):
    """
    Returns the Google Gemini LLM based on environment variables.
    
    Args:
        return_crew_llm (bool): If True, returns a crewai.LLM object (for Agents).
                               If False, returns a LangChain Chat object (for direct use/UI).
    """
    priority_model = os.getenv("CHOSEN_MODEL", "gemini-1.5-flash")
    api_key = os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        raise ValueError("Google API Key is not set. Please set GOOGLE_API_KEY environment variable.")
    
    if return_crew_llm:
        # Native CrewAI LLM for Gemini
        return LLM(
            model=f"gemini/{priority_model}",
            api_key=api_key
        )
    else:
        # LangChain wrapper for UI/Direct
        return ChatGoogleGenerativeAI(
            model=priority_model,
            verbose=True,
            temperature=0.7,
            google_api_key=api_key
        )



import google.generativeai as genai

def validate_api_key(key, provider):
    """Simple validation helper to set env vars"""
    if provider == "Google Gemini":
        os.environ["GOOGLE_API_KEY"] = key

def get_available_models(provider, api_key):
    """Fetch available models from the provider API."""
    try:
        if provider == "Google Gemini":
            genai.configure(api_key=api_key)
            # Filter for content generation models (removing embedding models etc)
            models = [
                m.name.replace("models/", "") 
                for m in genai.list_models() 
                if "generateContent" in m.supported_generation_methods
            ]
            return sorted(models)
            
    except Exception as e:
        print(f"Error fetching models: {e}")
        return []
    
    return []
