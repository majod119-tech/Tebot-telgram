import google.generativeai as genai
from config import GEMINI_API_KEY, AI_KNOWLEDGE

# استخدام الاتصال الخفيف لمنع التجميد
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY, transport="rest")

async def get_gemini_response(user_query):
    if not GEMINI_API_KEY:
        return "⚠️ عذراً، مفتاح GEMINI_API_KEY غير مضاف في إعدادات السيرفر."
    
    try:
        # 💡 التعديل 1: استخدام النموذج المستقر والمتوفر لجميع المفاتيح (gemini-pro)
        model = genai.GenerativeModel("gemini-pro")
        
        # 💡 التعديل 2: دمج شخصية المعلم مع السؤال برمجياً لضمان عملها على أي إصدار
        full_prompt = f"{AI_KNOWLEDGE}\n\nسؤال المتدرب: {user_query}"
        
        # الاتصال السريع
        response = await model.generate_content_async(full_prompt)
        
        if response and response.text:
            return response.text[:4000]
        else:
            return "⚠️ عذراً، لم أتمكن من صياغة إجابة مناسبة."

    except Exception as e:
        error_msg = str(e)
        print(f"Gemini API Error: {error_msg}")
        
        if "API_KEY" in error_msg or "400" in error_msg or "403" in error_msg:
            return "⚠️ خطأ: مفتاح الذكاء الاصطناعي غير صالح. يرجى التحقق منه في Koyeb."
            
        return f"⚠️ عطل فني في الذكاء الاصطناعي:\n{error_msg}"
