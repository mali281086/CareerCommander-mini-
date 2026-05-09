import os
import time
import base64
import tempfile
from tools.logger import logger
from tools.browser_manager import BrowserManager

class PDFGenerator:
    def __init__(self):
        pass

    def generate_cover_letter(self, ai_text, output_path=None):
        """
        Parses AI generated text and creates a professional PDF using Chrome's Print-to-PDF.
        This ensures the file size is > 8kb to bypass strict ATS empty-file filters.
        """
        from job_hunter.data_manager import DataManager
        config = DataManager().load_bot_config()
        
        prof = config.get("profile", {})
        contact_info = {
            "name": prof.get("name") or "Your Name",
            "address": prof.get("address") or "Your Address",
            "email": prof.get("email") or "your.email@example.com",
            "cell": prof.get("cell") or "+00 000 0000",
            "linkedin": prof.get("linkedin") or "https://linkedin.com/in/yourprofile",
            "github": prof.get("github") or "https://github.com/yourprofile"
        }

        if not output_path:
            output_path = config.get("settings", {}).get("cover_letter_path", "Cover_Letter.pdf")

        try:
            # If path is a directory, append default filename
            if os.path.isdir(output_path) or output_path.endswith("/") or output_path.endswith("\\"):
                # Clean up the name by removing spaces
                safe_name = contact_info['name'].replace(" ", "_") if contact_info['name'] != "Your Name" else "Cover_Letter"
                output_path = os.path.join(output_path, f"{safe_name}_Cover_Letter.pdf")
            
            # Ensure file extension
            if not output_path.lower().endswith(".pdf"):
                output_path += ".pdf"

            # Ensure directory exists
            parent_dir = os.path.dirname(output_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            # --- Extract Subject and Body ---
            lines = ai_text.strip().split("\n")
            subject = "Job Application"
            body_start_idx = 0

            for i, line in enumerate(lines):
                if line.lower().startswith("subject:"):
                    subject = line.replace("Subject:", "").replace("subject:", "").strip()
                    body_start_idx = i + 1
                    break

            body_lines = lines[body_start_idx:]
            clean_body = []
            
            # Common closing phrases to strip out
            closings = [
                "dear hiring team", "dear hiring manager", "dear hiring",
                "yours sincerely", "sincerely", "regards", "best regards", 
                "kind regards", "yours faithfully", "thank you", "sincerely yours"
            ]
            
            user_name_low = contact_info["name"].lower().strip()

            for line in body_lines:
                l_low = line.lower().strip()
                if not l_low:
                    continue # Skip empty lines since CSS margin-bottom handles spacing
                
                # Skip lines that are just closings or the user's own name
                if any(l_low == c or l_low.startswith(c + ",") or l_low.startswith(c + " ") for c in closings):
                    continue
                if l_low == user_name_low:
                    continue
                    
                clean_body.append(f"<p>{line}</p>")

            full_body = "".join(clean_body)

            # Build HTML template
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{
                        font-family: 'Helvetica', 'Arial', sans-serif;
                        font-size: 14px;
                        line-height: 1.6;
                        color: #000;
                        margin: 0;
                        padding: 0;
                    }}
                    .header {{
                        margin-bottom: 30px;
                    }}
                    .name {{
                        font-size: 20px;
                        font-weight: bold;
                        margin-bottom: 5px;
                    }}
                    .contact-info {{
                        font-size: 13px;
                        color: #333;
                    }}
                    .subject {{
                        font-weight: bold;
                        margin-bottom: 20px;
                        font-size: 15px;
                    }}
                    .salutation {{
                        margin-bottom: 15px;
                    }}
                    .body-content p {{
                        margin-top: 0;
                        margin-bottom: 15px;
                        text-align: justify;
                    }}
                    .footer {{
                        margin-top: 40px;
                    }}
                    .signature-name {{
                        font-weight: bold;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <div class="name">{contact_info["name"]}</div>
                    <div class="contact-info">
                        {contact_info["address"]}<br>
                        Email: {contact_info["email"]}<br>
                        Cell: {contact_info["cell"]}<br>
                        LinkedIn: {contact_info["linkedin"]}<br>
                        GitHub: {contact_info["github"]}
                    </div>
                </div>
                
                <div class="subject">
                    Subject: {subject}
                </div>
                
                <div class="salutation">
                    Dear Hiring Team,
                </div>
                
                <div class="body-content">
                    {full_body}
                </div>
                
                <div class="footer">
                    Yours sincerely,<br>
                    <div class="signature-name">{contact_info["name"]}</div>
                </div>
            </body>
            </html>
            """

            # Save HTML to temporary file
            with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html', encoding='utf-8') as f:
                f.write(html_content)
                temp_html_path = f.name

            # Use BrowserManager to print to PDF
            try:
                bm = BrowserManager()
                
                # Check if there's an already running browser to avoid the 10-second restart penalty
                driver = None
                original_window = None
                is_reused = False
                
                if getattr(bm, '_driver', None) is not None:
                    try:
                        bm._driver.title # Check if alive
                        driver = bm._driver
                        is_reused = True
                        original_window = driver.current_window_handle
                        driver.switch_to.new_window('tab')
                    except:
                        driver = None
                        
                if not driver:
                    # Fallback if no browser is currently active
                    driver = bm.get_driver(headless=True, profile_name="default")
                
                # Load the HTML file
                file_url = f"file:///{temp_html_path.replace(chr(92), '/')}"
                driver.get(file_url)
                
                # Small wait to ensure fonts/layout are fully rendered
                time.sleep(0.5)
                
                # Execute Chrome DevTools Protocol command to print to PDF
                # This embeds fonts and metadata, bumping the size well past 8kb
                pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {
                    "printBackground": True,
                    "marginTop": 0.5,
                    "marginBottom": 0.5,
                    "marginLeft": 0.5,
                    "marginRight": 0.5,
                    "paperWidth": 8.5,
                    "paperHeight": 11.0
                })
                
                # Write decoded base64 to output path
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(pdf_data['data']))
                    
                # Clean up tab if we reused an existing browser
                if is_reused and original_window:
                    try:
                        driver.close()
                        driver.switch_to.window(original_window)
                    except: pass
                    
            finally:
                # Cleanup temp HTML file
                try:
                    os.remove(temp_html_path)
                except:
                    pass

            logger.info(f"✅ CareerCommander: Cover Letter PDF printed via Chrome at {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"❌ CareerCommander: Failed to generate PDF via Chrome: {e}")
            return None

# Singleton-like helper
_generator = PDFGenerator()
def generate_cover_letter_pdf(text_content, output_path=None):
    if output_path:
        return _generator.generate_cover_letter(text_content, output_path=output_path)
    return _generator.generate_cover_letter(text_content)
