import asyncio
import google.generativeai as genai
from config import GEMINI_API_KEY, AI_KNOWLEDGE

# إعداد مفتاح API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# دالة متزامنة مخفية للاتصال بجوجل (تعمل في الخلفية)
def _fetch_gemini_sync(query):
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=AI_KNOWLEDGE
    )
    return model.generate_content(query).text

# الدالة الأساسية التي يكلمها البوت
async def get_gemini_response(user_query):
    if not GEMINI_API_KEY:
        return "⚠️ عذراً، مفتاح GEMINI_API_KEY غير موجود في إعدادات Koyeb."
    
    try:
        # 💡 السر هنا: تشغيل الاتصال بجوجل في مسار (Thread) منفصل تماماً حتى لا يتجمد تليجرام
        response_text = await asyncio.to_thread(_fetch_gemini_sync, user_query)
        
        if response_text:
            return response_text[:4000]
        else:
            return "لم أتمكن من صياغة إجابة، يرجى إعادة المحاولة."

    except Exception as e:
        error_msg = str(e)
        print(f"Gemini Error: {error_msg}")
        
        # إذا كان الخطأ بسبب المفتاح، سيخبرك البوت فوراً
        if "API_KEY" in error_msg or "400" in error_msg or "403" in error_msg:
            return "⚠️ خطأ: مفتاح الذكاء الاصطناعي (API Key) غير صالح أو منتهي. يرجى التحقق منه في Koyeb."
        
        # أي خطأ آخر سيظهر لك هنا ولن يعلق البوت
        return f"⚠️ عطل فني في الذكاء الاصطناعي:\n{error_msg}"
