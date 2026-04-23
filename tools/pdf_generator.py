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

    def generate_cover_letter(self, ai_text, output_path="data/generated_cover_letter.pdf"):
        """
        Parses AI generated text and creates a professional PDF.
        AI text usually contains 'Subject: ...' and the body.
        """
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

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
            # Reconstruct body skipping salutation if AI already included it
            body_lines = lines[body_start_idx:]
            clean_body = []
            for line in body_lines:
                l_low = line.lower().strip()
                if any(x in l_low for x in ["dear hiring team", "dear hiring manager", "yours sincerely"]):
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
def generate_cover_letter_pdf(text_content):
    return _generator.generate_cover_letter(text_content)
