import os
import io
import json
from datetime import datetime
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

# استدعاء الإعدادات والقوائم
from bot_settings import GROUP_ID, INTERROGATIONS_FILE, SEP
from menus import get_main_menu, get_pledge_step2_menu, get_pledge_step3_menu

# استدعاء مكتبة الصور للختم الآلي
try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# دوال مساعدة لقراءة وحفظ الملفات
def load_json_local(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file: return json.load(file)
        except: return {}
    return {}

def save_json_local(f, d): 
    try:
        with open(f, "w", encoding="utf-8") as file: json.dump(d, file, ensure_ascii=False)
    except: pass

# ==========================================
# 1. محرك الإقرارات (التعهدات)
# ==========================================
async def process_pledge_step(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, text, state, user_states):
    step = state['step']
    
    if step == 1:
        user_states[user_id]['aware'] = text
        user_states[user_id]['step'] = 2
        return await update.message.reply_text("2️⃣ *فضلاً، اختر العذر الرئيسي لكثرة غياباتك من القائمة بالأسفل:*\n(أو يمكنك كتابة عذرك يدوياً)", parse_mode='Markdown', reply_markup=get_pledge_step2_menu())
    
    elif step == 2:
        if len(text) < 4: return await update.message.reply_text("⚠️ العذر غير واضح، اختر من الأزرار بالأسفل أو اكتب عذراً مفصلاً:", reply_markup=get_pledge_step2_menu())
        user_states[user_id]['excuse'] = text
        user_states[user_id]['step'] = 3
        return await update.message.reply_text("3️⃣ *الإقرار النهائي:*\nهل تتعهد بالانضباط والالتزام لتفادي الحرمان النهائي (20%) وطي القيد؟\n*(اضغط على زر التعهد بالأسفل)*", parse_mode='Markdown', reply_markup=get_pledge_step3_menu())
    
    elif step == 3:
        if "تعهد" not in text and "أقر" not in text and "نعم" not in text:
            return await update.message.reply_text("⚠️ لم يتم قبول إقرارك!\nيرجى الضغط على زر الإقرار بالأسفل للموافقة:", reply_markup=get_pledge_step3_menu())
        
        completed = load_json_local(INTERROGATIONS_FILE)
        completed.setdefault(state['stu_num'], []).append(state['subject'])
        save_json_local(INTERROGATIONS_FILE, completed)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        official_document = f"🏛️ **المؤسسة العامة للتدريب التقني والمهني**\n📍 **المعهد الصناعي الثانوي ببريدة - قسم الحاسب**\n{SEP}\n📄 **وثيقة تعهد إلكتروني بالانضباط الأكاديمي**\nأقر وأتعهد أنا المتدرب / **{state['stu_nam']}**\nالرقم التدريبي / **{state['stu_num']}**\nبشأن المقرر التدريبي / **{state['subject']}**\nبأنني اطلعت على نسبة غيابي التي بلغت حد (الإنذار)، وأتعهد بالانضباط التام.\n📝 **العذر المُسجل للمتدرب:** {state['excuse']}\n✅ **حالة الاعتماد:** (مُعتمد ومُوقع إلكترونياً من قبل المتدرب)\n⏱️ **تاريخ وتوثيق الاعتماد:** {timestamp}\n{SEP}"
        
        try: await context.bot.send_message(chat_id=GROUP_ID, text=official_document, parse_mode='Markdown')
        except Exception as e: pass 
        
        del user_states[user_id]
        await update.message.reply_text(official_document, parse_mode='Markdown')
        await update.message.reply_text("✅ *تم توثيق إقرارك رسمياً ورفع نسخة للإدارة.*\nاحرص على الحضور لتفادي طي القيد.", parse_mode='Markdown', reply_markup=get_main_menu())

# ==========================================
# 2. محرك الختم الآلي للأعذار (الصور والملفات)
# ==========================================
async def process_excuse_document(update: Update, context: ContextTypes.DEFAULT_TYPE, user_states):
    user_id = str(update.effective_user.id)
    caption_text = update.message.caption
    stu_id = ''.join(filter(str.isdigit, str(caption_text)))
    
    if not caption_text or len(stu_id) < 5:
        return await update.message.reply_text("🛑 *مرفوض: وصف غير مكتمل!*\nيجب كتابة *رقمك التدريبي* في الوصف.", parse_mode='Markdown')
        
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
    status_msg = await update.message.reply_text("⏳ جاري الختم الآلي والإرسال للإدارة...")
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if update.message.photo and HAS_PIL:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            in_memory_img = io.BytesIO()
            await file.download_to_memory(in_memory_img)
            in_memory_img.seek(0)
            
            img = Image.open(in_memory_img)
            txt_img = Image.new('RGB', (1000, 50), color='#1e3a8a')
            ImageDraw.Draw(txt_img).text((20, 15), f"TVTC OFFICIAL | ID: {stu_id} | DATE: {timestamp}", fill="white")
            txt_img = txt_img.resize((img.size[0], int(img.size[0] * 50 / 1000)))
            img.paste(txt_img, (0, img.size[1] - txt_img.height)) 
            
            output = io.BytesIO()
            img.save(output, format='JPEG')
            output.seek(0)
            await context.bot.send_photo(chat_id=GROUP_ID, photo=output, caption=f"📥 *عذر مختوم:*\n{caption_text}\n⏱️ {timestamp}", parse_mode='Markdown')
        else: 
            await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 *عذر مرفق:*\n{caption_text}\n{timestamp}", parse_mode='Markdown')
            
        if user_id in user_states: del user_states[user_id]
        await status_msg.edit_text("✅ *تم الختم والإرسال للإدارة بنجاح.*", parse_mode='Markdown')
    except Exception as e: 
        await status_msg.edit_text(f"⚠️ خطأ فني مباشر من السيرفر:\n`{str(e)}`", parse_mode='Markdown')
