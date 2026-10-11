import google.generativeai as genai
from config import GEMINI_API_KEY, AI_KNOWLEDGE

# إعداد مفتاح الـ API لـ Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_gemini_response(user_query):
    # إذا لم يكن المفتاح موجوداً في Koyeb
    if not GEMINI_API_KEY:
        return "⚠️ عذراً، مفتاح GEMINI_API_KEY غير مضاف في إعدادات السيرفر. يرجى إضافته أولاً."
    
    try:
        # استخدام نموذج Gemini مع التعليمات الخاصة التي أعددناها في config.py
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=AI_KNOWLEDGE
        )
        
        # توليد الإجابة
        response = model.generate_content(user_query)
        return response.text

    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "عذراً، أواجه ضغطاً في الاستفسارات حالياً ⏳. حاول طرح سؤالك بصيغة أخرى بعد قليل."
