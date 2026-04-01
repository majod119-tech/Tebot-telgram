import io
from datetime import datetime
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from bot_settings import *
from menus import *

# استدعاء مكتبة الصور للختم
try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# --- 🌟 محرك الختم الآلي ومعالجة الأعذار 🌟 ---
async def handle_student_docs(update: Update, context: ContextTypes.DEFAULT_TYPE, user_states):
    user_id = str(update.effective_user.id)
    caption = update.message.caption
    stu_id = ''.join(filter(str.isdigit, str(caption))) if caption else ""
    
    if not caption or len(stu_id) < 5:
        return await update.message.reply_text("🛑 *مرفوض:* يجب كتابة رقمك التدريبي في وصف الصورة ليتم الختم والربط.", parse_mode='Markdown')
        
    status_msg = await update.message.reply_text("⏳ جاري التحقق والختم الآلي...")
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if update.message.photo and HAS_PIL:
            file = await context.bot.get_file(update.message.photo[-1].file_id)
            in_mem = io.BytesIO()
            await file.download_to_memory(in_mem); in_mem.seek(0)
            
            img = Image.open(in_mem)
            # إضافة شريط الختم الرسمي لقسم الحاسب ببريدة
            txt_img = Image.new('RGB', (1000, 50), color='#1e3a8a')
            draw = ImageDraw.Draw(txt_img)
            draw.text((20, 15), f"TVTC BURAYDAH | COMPUTER DEPT | ID: {stu_id} | DATE: {timestamp}", fill="white")
            txt_img = txt_img.resize((img.size[0], int(img.size[0] * 50 / 1000)))
            img.paste(txt_img, (0, img.size[1] - txt_img.height)) 
            
            out = io.BytesIO(); img.save(out, format='JPEG'); out.seek(0)
            await context.bot.send_photo(chat_id=GROUP_ID, photo=out, caption=f"📥 *عذر مختوم:* {caption}\n⏱️ {timestamp}", parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=GROUP_ID, text=f"📥 *عذر مرفق:* {caption}\n{timestamp}", parse_mode='Markdown')
            
        if user_id in user_states: del user_states[user_id]
        await status_msg.edit_text("✅ *تم الاعتماد والختم والإرسال للإدارة بنجاح.*", parse_mode='Markdown')
    except Exception as e:
        await status_msg.edit_text(f"⚠️ خطأ فني في الختم: {e}")

# --- 🌟 محرك الإقرارات والتعهدات 🌟 ---
async def handle_pledge_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, text, state, user_states):
    if state['step'] == 1:
        user_states[user_id].update({'aware': text, 'step': 2})
        return await update.message.reply_text("2️⃣ *فضلاً، اختر العذر الرئيسي للغياب من القائمة:*", parse_mode='Markdown', reply_markup=get_pledge_step2_menu())
    
    elif state['step'] == 2:
        user_states[user_id].update({'excuse': text, 'step': 3})
        return await update.message.reply_text("3️⃣ *الإقرار النهائي:*\nهل تتعهد بالانضباط لتفادي الحرمان (20%)؟", parse_mode='Markdown', reply_markup=get_pledge_step3_menu())
    
    elif state['step'] == 3:
        if "تعهد" not in text and "أقر" not in text and "نعم" not in text:
            return await update.message.reply_text("⚠️ يرجى الضغط على زر الإقرار بالأسفل للموافقة:", reply_markup=get_pledge_step3_menu())
        
        # توثيق التعهد في ملف الإدارة
        comp = load_json(INTERROGATIONS_FILE)
        comp.setdefault(state['stu_num'], []).append(state['subject'])
        save_json(INTERROGATIONS_FILE, comp)
        
        doc = f"📄 **وثيقة تعهد إلكتروني**\nالمتدرب: **{state['stu_nam']}**\nالمقرر: **{state['subject']}**\nالعذر: {state['excuse']}\nالتاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        try: await context.bot.send_message(chat_id=GROUP_ID, text=doc, parse_mode='Markdown')
        except: pass 
        
        del user_states[user_id]
        return await update.message.reply_text(doc + "\n✅ *تم توثيق إقرارك رسمياً.*", parse_mode='Markdown', reply_markup=get_main_menu())
