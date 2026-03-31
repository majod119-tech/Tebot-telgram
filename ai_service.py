def extract_text_from_pdf_bytes(pdf_bytes):
    """استخراج النص من ملف PDF وتلميعه وتنظيفه"""
    text = ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        # 🟢 فلتر التنظيف: إزالة الرموز المخفية اللي تعطل الذكاء الاصطناعي
        text = text.replace('\x00', '').replace('\ufffd', '')
    except Exception as e:
        print(f"⚠️ خطأ في قراءة الـ PDF: {e}")
    return text
