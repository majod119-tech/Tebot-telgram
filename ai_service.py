import PyPDF2
import io
from datetime import datetime
import requests

def ask_openclaw_api(user_message):
    # ⚠️ استبدل هذا الرابط برابط سيرفر OpenClaw حقك
    API_URL = "https://your-openclaw-server-url.com/api/chat" 
    
    try:
        # إرسال الطلب للسيرفر (ننتظر 30 ثانية كحد أقصى)
        response = requests.post(API_URL, json={"message": user_message}, timeout=30)
        
        # 🛡️ الدرع الأول: السيرفر متصل لكنه زعلان (رفض الطلب)
        if response.status_code != 200:
            return f"⚠️ **السيرفر رفض الطلب!**\nكود الخطأ: `{response.status_code}`\nرسالة السيرفر: `{response.text[:150]}`"

        # 🛡️ الدرع الثاني: تفكيك الرد (هنا كان يصير انهيار CSV)
        try:
            data = response.json()
            # حاول تجيب الرد من حقل response أو answer حسب برمجة سيرفرك
            return data.get("response", data.get("answer", "✅ السيرفر رد، لكن لم أجد الإجابة داخل البيانات."))
            
        except requests.exceptions.JSONDecodeError:
            return f"⚠️ **خطأ في صيغة الرد!** السيرفر رد بنص عادي (ليس JSON).\nشكل الرد: `{response.text[:150]}...`"

    # 🛡️ الدرع الثالث: السيرفر ما يرد (ميت)
    except requests.exceptions.Timeout:
        return "⚠️ **انتهى الوقت (Timeout)!** سيرفر OpenClaw عليه ضغط أو مغلق."
        
    # 🛡️ الدرع الرابع: الرابط غلط أو السيرفر محذوف
    except requests.exceptions.ConnectionError:
        return "⚠️ **فشل الاتصال!** تأكد أن رابط سيرفر OpenClaw يعمل وأن السيرفر قيد التشغيل."
        
    except Exception as e:
        return f"⚠️ **خطأ غير متوقع:** `{str(e)}`"


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

def save_knowledge_to_db(db, file_name, text):
    """حفظ النصوص في قاعدة بيانات MongoDB (بنك المعرفة)"""
    kb_col = db["knowledge_base"]
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
