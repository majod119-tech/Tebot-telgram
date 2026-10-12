import asyncio
import google.generativeai as genai
from config import GEMINI_API_KEY, AI_KNOWLEDGE

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# متغير لحفظ اسم النموذج الصحيح حتى لا نبحث عنه في كل مرة
AVAILABLE_MODEL = None

async def get_gemini_response(user_query):
    global AVAILABLE_MODEL
    
    if not GEMINI_API_KEY:
        return "⚠️ عذراً، مفتاح GEMINI_API_KEY غير مضاف في إعدادات السيرفر."
    
    try:
        # 1. الاكتشاف التلقائي للنموذج المتاح لمفتاحك
        if not AVAILABLE_MODEL:
            def find_valid_model():
                # جلب كل النماذج المسموحة لمفتاحك واختيار أول نموذج يدعم الدردشة
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        return m.name
                return None
            
            # تشغيل البحث في مسار آمن لمنع التجميد
            AVAILABLE_MODEL = await asyncio.to_thread(find_valid_model)
            
            if not AVAILABLE_MODEL:
                return "⚠️ خطأ: حسابك في منصة Google لا يحتوي على أي نماذج مفعّلة للدردشة حالياً."

        # 2. بناء الطلب باستخدام النموذج الذي اكتشفناه
        model = genai.GenerativeModel(AVAILABLE_MODEL)
        full_prompt = f"{AI_KNOWLEDGE}\n\nسؤال المتدرب: {user_query}"
        
        # 3. إرسال السؤال
        response = await model.generate_content_async(full_prompt)
        
        if response and response.text:
            return response.text[:4000]
        else:
            return "⚠️ عذراً، لم أتمكن من صياغة إجابة مناسبة."

    except Exception as e:
        error_msg = str(e)
        return f"⚠️ خطأ فني (تمت المحاولة باستخدام النموذج: {AVAILABLE_MODEL}):\n{error_msg}"
