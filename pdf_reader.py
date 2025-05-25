import fitz  # PyMuPDF

def extract_text_from_pdf(file_stream):
    pdf_document = fitz.open(stream=file_stream, filetype="pdf")  
    
    text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document.load_page(page_num)
        text += page.get_text()

    return text
