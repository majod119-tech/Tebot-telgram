import PyPDF2
import io
from datetime import datetime

def extract_text_from_pdf_bytes(pdf_bytes):
    """استخراج النص من ملف PDF في الذاكرة"""
    text = ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as e:
        print(f"⚠️ خطأ في قراءة الـ PDF: {e}")
    return text

def save_knowledge_to_db(db, file_name, text):
    """حفظ النصوص في قاعدة بيانات MongoDB (بنك المعرفة)"""
    kb_col = db["knowledge_base"]
    # استخدمنا update_one عشان لو رفعت ملف بنفس الاسم يتحدث وما يتكرر
    kb_col.update_one(
        {"file_name": file_name},
        {"$set": {"text": text, "updated_at": datetime.now()}},
        upsert=True
    )

def get_all_knowledge(db):
    """جلب كل المراجع واللوائح المحفوظة من MongoDB"""
    try:
        kb_col = db["knowledge_base"]
        docs = kb_col.find({})
        full_text = ""
        for doc in docs:
            full_text += f"\n--- مرجع: {doc['file_name']} ---\n{doc.get('text', '')}\n"
        return full_text
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال بالقاعدة: {e}")
        return ""

def build_ai_prompt(db, base_knowledge, user_question):
    """دمج المراجع من قاعدة البيانات مع سؤال المتدرب"""
    guide_text = get_all_knowledge(db)
    
    if guide_text.strip():
        return f"{base_knowledge}\n\nالمراجع الرسمية للمؤسسة (بنك المعرفة):\n{guide_text}\n\nبناءً على المراجع أعلاه، أجب على سؤال المتدرب بدقة واحترافية: {user_question}"
    else:
        return f"{base_knowledge}\nسؤال: {user_question}"
