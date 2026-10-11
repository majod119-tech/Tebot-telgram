import asyncio
import google.generativeai as genai
from config import GEMINI_API_KEY, AI_KNOWLEDGE

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def get_gemini_response(user_query):
    if not GEMINI_API_KEY:
        return "⚠️ عذراً، مفتاح GEMINI_API_KEY غير مضاف في إعدادات السيرفر."
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=AI_KNOWLEDGE
        )
        
        # فصل عملية الذكاء الاصطناعي في مسار (Thread) مستقل لمنع تجميد البوت
        response = await asyncio.to_thread(model.generate_content, user_query)
        
        try:
            return response.text[:4000]
        except Exception:
            return "عذراً، لم أتمكن من صياغة إجابة مناسبة."

    except Exception as e:
        print(f"Gemini API Error: {e}")
        # سيتم عرض الخطأ لك في البوت مباشرة لتعرف سبب المشكلة!
        return f"⚠️ حدث خطأ في الاتصال بالذكاء الاصطناعي:\n`{e}`"
