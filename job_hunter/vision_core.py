import os
import json
import time
import google.generativeai as genai
from tools.logger import logger
from PIL import Image
import io

# Reduce prompt size slightly by removing fluff and focusing on strictness
VISION_PROMPT = """
Analyze the provided web UI screenshot and the user's resume text to progress a job application.
The screenshot is from a browser viewport. Use 2D normalized coordinates [ymin, xmin, ymax, xmax] (0-1000 scale).

STRICT JSON OUTPUT:
{
  "page_purpose": "Brief description",
  "status": "continue | error | success | review_needed",
  "human_intervention_needed": boolean,
  "intervention_reason": "Required if human_intervention_needed is true",
  "actions": [
      {
          "type": "click | type | scroll | pause | upload",
          "reason": "Why?",
          "coordinates": [ymin, xmin, ymax, xmax],
          "text_to_type": "Data if 'type' set",
          "file_to_upload": "resume | cover_letter"
      }
  ]
}

RULES:
- If 'Submit' or 'Review' page, set human_intervention_needed=true.
- If no progress possible or stuck, return 'scroll' actions or set human_intervention_needed=true.
- Coordinates relate purely to visual elements in the screenshot.

RESUME CONTENT:
{resume_text}
"""

class VisionCore:
    def __init__(self):
        # Support both standard names
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        
        if not api_key:
            logger.warning("No Gemini/Google API Key found in environment. Vision Applier will fail.")
        else:
            genai.configure(api_key=api_key)
            
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"response_mime_type": "application/json"}
        )
    
    def _prepare_image(self, screenshot_path, max_dim=1024):
        """Resizes and compresses image to minimize tokens/payload while keeping UI readable."""
        with Image.open(screenshot_path) as img:
            # Convert to RGB if needed (JPEG doesn't support RGBA)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
            
            # Save to buffer with compression
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75, optimize=True)
            return Image.open(buf)

    def get_vision_decision(self, screenshot_path, resume_text, retries=2):
        last_error = None
        for attempt in range(retries + 1):
            try:
                # Add human jitter delay to respect RPM limits on free tier
                if attempt > 0:
                    wait_time = (attempt * 5) # 5s, 10s backoff
                    logger.info(f"Retrying Vision API call in {wait_time}s... (Attempt {attempt+1})")
                    time.sleep(wait_time)
                
                prompt = VISION_PROMPT.format(resume_text=str(resume_text))
                processed_img = self._prepare_image(screenshot_path)
                
                response = self.model.generate_content([prompt, processed_img])
                
                raw_text = response.text
                return json.loads(raw_text.strip())
            
            except Exception as e:
                last_error = str(e)
                if "429" in last_error or "quota" in last_error.lower():
                    logger.warning(f"[VisionCore] Rate limit hit on attempt {attempt+1}")
                    continue
                else:
                    break # Don't retry non-quota errors
        
        logger.error(f"[VisionCore] API Error after {attempt+1} attempts: {last_error}")
        return {
            "status": "error", 
            "human_intervention_needed": True, 
            "intervention_reason": f"AI API Error: {last_error}", 
            "actions": []
        }
