import pdfplumber

def parse_resume(file_obj):
    """
    Extracts text from a PDF file object (stream) or path.
    """
    text = ""
    try:
        with pdfplumber.open(file_obj) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        return f"Error reading PDF: {str(e)}"
    
    return text
