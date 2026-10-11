import google.generativeai as genai
from config import GEMINI_API_KEY, AI_KNOWLEDGE

# إعداد مفتاح الـ API لـ Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# أضفنا كلمة async هنا
async def get_gemini_response(user_query):
    # إذا لم يكن المفتاح موجوداً في Koyeb
    if not GEMINI_API_KEY:
        return "⚠️ عذراً، مفتاح GEMINI_API_KEY غير مضاف في إعدادات السيرفر. يرجى إضافته أولاً."
    
    try:
        # استخدام نموذج Gemini مع التعليمات الخاصة التي أعددناها
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=AI_KNOWLEDGE
        )
        
        # أضفنا await واستخدمنا generate_content_async لعدم تجميد البوت
        response = await model.generate_content_async(user_query)
        
        # التأكد من عدم وجود أخطاء في الرد وتحديد طوله لتليجرام
        try:
            return response.text[:4000]
        except ValueError:
            return "عذراً، لم أتمكن من صياغة إجابة مناسبة. حاول طرح سؤالك بصيغة أخرى."

    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "عذراً، أواجه ضغطاً في الاستفسارات حالياً ⏳. حاول طرح سؤالك بصيغة أخرى بعد قليل."
