import google.generativeai as genai
from config import GEMINI_API_KEY, AI_KNOWLEDGE

if GEMINI_API_KEY:
    # إعداد المفتاح بدون تحديد نوع النقل (transport) لندع المكتبة تتولى الطريقة الأنسب للمفتاح الجديد
    genai.configure(api_key=GEMINI_API_KEY)

async def get_gemini_response(user_query):
    if not GEMINI_API_KEY:
        return "⚠️ عذراً، مفتاح GEMINI_API_KEY غير مضاف في إعدادات السيرفر."
    
    try:
        # استخدام النموذج الأساسي مع التعليمات المدمجة
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # دمج التعليمات مع السؤال لتجنب أي تعارض في البنية
        full_prompt = f"{AI_KNOWLEDGE}\n\nسؤال المتدرب: {user_query}"
        
        # استخدام الدالة غير المتزامنة
        response = await model.generate_content_async(full_prompt)
        
        if response and response.text:
            return response.text[:4000]
        else:
            return "⚠️ عذراً، لم أتمكن من صياغة إجابة مناسبة."

    except Exception as e:
        error_msg = str(e)
        print(f"Gemini API Error: {error_msg}")
        return f"⚠️ خطأ فني أثناء الاتصال بالذكاء الاصطناعي:\n{error_msg}"
