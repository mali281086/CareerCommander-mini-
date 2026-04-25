import os
from fpdf import FPDF
from tools.logger import logger

class PDFGenerator:
    def __init__(self):
        # Static contact info as requested by user
        self.contact_info = {
            "name": "Sheikh Ali Mateen",
            "address": "Berlin, Germany",
            "email": "m.ali281086@gmail.com",
            "cell": "+49 176 2698 3236",
            "linkedin": "https://www.linkedin.com/in/sm-ali",
            "github": "github.com/mali281086"
        }

    def generate_cover_letter(self, ai_text, output_path="data/Cover_Letter.pdf"):
        """
        Parses AI generated text and creates a professional PDF.
        """
        try:
            # If path is a directory, append default filename
            if os.path.isdir(output_path) or output_path.endswith("/") or output_path.endswith("\\"):
                output_path = os.path.join(output_path, "Cover_Letter.pdf")
            
            # Ensure file extension
            if not output_path.lower().endswith(".pdf"):
                output_path += ".pdf"

            # Sanitize text for FPDF
            ai_text = ai_text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-")
            
            # Ensure directory exists
            parent_dir = os.path.dirname(output_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # Use standard fonts
            pdf.set_font("Helvetica", size=10)

            # --- Header: User Contact Info ---
            pdf.set_font("Helvetica", style="B", size=12)
            pdf.cell(0, 7, self.contact_info["name"], ln=True, align="L")
            
            pdf.set_font("Helvetica", size=10)
            pdf.cell(0, 5, self.contact_info["address"], ln=True, align="L")
            pdf.cell(0, 5, f"Email: {self.contact_info['email']}", ln=True, align="L")
            pdf.cell(0, 5, f"Cell: {self.contact_info['cell']}", ln=True, align="L")
            pdf.cell(0, 5, f"LinkedIn: {self.contact_info['linkedin']}", ln=True, align="L")
            pdf.cell(0, 5, f"GitHub: {self.contact_info['github']}", ln=True, align="L")
            
            pdf.ln(10) # Spacer

            # --- Extract Subject and Body ---
            lines = ai_text.strip().split("\n")
            subject = "Job Application"
            body_start_idx = 0

            for i, line in enumerate(lines):
                if line.lower().startswith("subject:"):
                    subject = line.replace("Subject:", "").strip()
                    body_start_idx = i + 1
                    break
            
            # --- Subject Line ---
            pdf.set_font("Helvetica", style="B", size=11)
            pdf.multi_cell(0, 7, f"Subject: {subject}")
            pdf.ln(5)

            # --- Salutation ---
            pdf.set_font("Helvetica", size=11)
            pdf.cell(0, 7, "Dear Hiring Team,", ln=True)
            pdf.ln(2)

            # --- Body ---
            # Reconstruct body skipping salutation and common closings if AI already included them
            body_lines = lines[body_start_idx:]
            clean_body = []
            
            # Common closing phrases to strip out
            closings = [
                "dear hiring team", "dear hiring manager", "dear hiring",
                "yours sincerely", "sincerely", "regards", "best regards", 
                "kind regards", "yours faithfully", "thank you", "sincerely yours"
            ]
            
            user_name_low = self.contact_info["name"].lower().strip()

            for line in body_lines:
                l_low = line.lower().strip()
                if not l_low:
                    clean_body.append("") # Keep empty lines for spacing
                    continue
                
                # Skip lines that are just closings or the user's own name
                if any(l_low == c or l_low.startswith(c + ",") or l_low.startswith(c + " ") for c in closings):
                    continue
                if l_low == user_name_low:
                    continue
                    
                clean_body.append(line)

            full_body = "\n".join(clean_body).strip()
            pdf.multi_cell(0, 6, full_body)
            
            pdf.ln(10)

            # --- Footer ---
            pdf.cell(0, 7, "Yours sincerely,", ln=True)
            pdf.set_font("Helvetica", style="B", size=11)
            pdf.cell(0, 7, self.contact_info["name"], ln=True)

            # Save
            pdf.output(output_path)
            logger.info(f"✅ CareerCommander: Cover Letter PDF generated at {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"❌ CareerCommander: Failed to generate PDF: {e}")
            return None

# Singleton-like helper
_generator = PDFGenerator()
def generate_cover_letter_pdf(text_content, output_path=None):
    if output_path:
        return _generator.generate_cover_letter(text_content, output_path=output_path)
    return _generator.generate_cover_letter(text_content)
