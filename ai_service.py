import os
import PyPDF2

# متغير لتخزين النص في الذاكرة عشان ما يقرأ الملف مع كل سؤال (تسريع الأداء)
TRAINEE_GUIDE_TEXT = ""

def load_pdf_knowledge():
    """دالة تقرأ ملف PDF وتخزنه في الذاكرة"""
    global TRAINEE_GUIDE_TEXT
    if os.path.exists("trainee_guide.pdf"):
        try:
            with open("trainee_guide.pdf", "rb") as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                TRAINEE_GUIDE_TEXT = text
                print("✅ تم تلقين الذكاء الاصطناعي بدليل المتدرب بنجاح!")
        except Exception as e:
            print(f"⚠️ خطأ في قراءة الدليل: {e}")
    return TRAINEE_GUIDE_TEXT

def build_ai_prompt(base_knowledge, user_question):
    """دالة تدمج سؤال المتدرب مع الدليل الرسمي"""
    guide_text = TRAINEE_GUIDE_TEXT if TRAINEE_GUIDE_TEXT else load_pdf_knowledge()
    
    if guide_text:
        return f"{base_knowledge}\n\nالمرجع الرسمي (دليل المتدرب):\n{guide_text}\n\nبناءً على المرجع أعلاه، أجب على سؤال المتدرب بدقة واحترافية: {user_question}"
    else:
        return f"{base_knowledge}\nسؤال: {user_question}"
