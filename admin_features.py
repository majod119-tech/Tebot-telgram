import os
import io
import json
import base64
import requests
import pandas as pd
from datetime import datetime
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

# 🔴 استدعاء القائمة الإدارية المحدثة 🔴
from menus import get_admin_menu

# --- 🌟 ثوابت الإدارة 🌟 ---
ADMIN_ID = "10073498"
SEP = "━━━━━━━━━━━━━━"
STATS_FILE = "stats.json"
INTERROGATIONS_FILE = "interrogations.json"

# دوال مساعدة خاصة بملف الإدارة
def load_json_admin(f): 
    if os.path.exists(f):
        try:
            with open(f, "r", encoding="utf-8") as file: return json.load(file)
        except: return {}
    return {}

def backup_to_github(file_path="data.xlsx"):
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repo = os.environ.get("GITHUB_REPO")
    if not github_token or not github_repo: return "⚠️ (حفظ محلي مؤقت، السحابة غير مربوطة)."
    
    url = f"https://api.github.com/repos/{github_repo}/contents/{file_path}"
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    try:
        sha = None
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200: sha = resp.json().get("sha")
        with open(file_path, "rb") as f: content = base64.b64encode(f.read()).decode("utf-8")
        data = {"message": f"تحديث قاعدة البيانات - {datetime.now().strftime('%Y-%m-%d %H:%M')}", "content": content}
        if sha: data["sha"] = sha
        put_resp = requests.put(url, headers=headers, json=data)
        if put_resp.status_code in [200, 201]: return "✅ **تم التثبيت الدائم في GitHub!**"
        else: return "⚠️ فشل الرفع لـ GitHub."
    except: return "⚠️ خطأ بالاتصال بـ GitHub."

# --- 🌟 أوامر المدير 🌟 ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    
    # هنا كان الخطأ: استبدلناه بالاستدعاء المباشر للقائمة المحدثة
    await update.message.reply_text("مرحباً بك يا رئيس القسم. تم فتح لوحة التحكم المتقدمة.", reply_markup=get_admin_menu())

async def db_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    try:
        if not os.path.exists('data.xlsx'):
            await update.message.reply_text("⚠️ لا يوجد ملف بيانات.")
            return
        df = pd.read_excel('data.xlsx', dtype=str)
        sample = df['stu_num'].dropna().unique()[:5]
        msg = f"📊 *كشاف البيانات:*\n✅ تم حفظ: {len(df)} سجل.\n🔍 عينة أرقام:\n`{', '.join(sample)}`"
        await update.message.reply_text(msg, parse_mode='Markdown')
    except: pass

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    await update.message.reply_text("⏳ جاري التجهيز...")
    for f in ['data.xlsx', 'scores.json', 'interrogations.json', 'stats.json', 'plans.json']:
        if os.path.exists(f): await context.bot.send_document(chat_id=update.effective_chat.id, document=open(f, 'rb'))

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    text = update.message.text.replace('/broadcast', '').strip()
    if not text: return await update.message.reply_text("⚠️ الطريقة: `/broadcast التعميم هنا`", parse_mode='Markdown')
    users = load_json_admin(STATS_FILE).get("users_list", [])
    await update.message.reply_text(f"📢 جاري الإرسال لـ {len(users)}...")
    for u in users:
        try: await context.bot.send_message(chat_id=u, text=f"📢 *إعلان إداري هام:*\n{SEP}\n{text}", parse_mode='Markdown')
        except: pass
    await update.message.reply_text("✅ تم إرسال التعميم.")

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return
    if str(update.effective_user.id) != ADMIN_ID: return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    stats = load_json_admin(STATS_FILE)
    interrogations = load_json_admin(INTERROGATIONS_FILE)
    
    users_count = len(stats.get("users_list", []))
    ai_queries = stats.get("ai_questions", 0)
    quiz_attempts = stats.get("quiz_attempts", 0)
    pledges_count = sum(len(subjects) for subjects in interrogations.values())
    
    db_records = 0
    active_students_count = 0
    weekly_attendance_rate = 100.0
    
    if os.path.exists('data.xlsx'):
        try: 
            df = pd.read_excel('data.xlsx', dtype=str)
            db_records = len(df)
            active_rows = df[~df['parsnt'].astype(str).str.contains('ح|ط|حرمان|طي', na=False)]
            active_students_count = active_rows['stu_num'].nunique()
            valid_absence = pd.to_numeric(df['parsnt'].astype(str).str.replace('%', ''), errors='coerce')
            valid_absence = valid_absence.dropna()
            if not valid_absence.empty:
                avg_absence = valid_absence.mean()
                weekly_attendance_rate = round(100 - avg_absence, 2)
        except: pass
        
    saved_minutes_ai = ai_queries * 3
    saved_minutes_pledges = pledges_count * 15
    total_hours_saved = round((saved_minutes_ai + saved_minutes_pledges) / 60, 1)
    
    report_msg = f"""
🏆 *تقرير الأداء لجائزة التميز بمنطقة القصيم* 🏆
{SEP}
👥 *المؤشرات الأكاديمية (محدثة آلياً):*
🔹 المتدربين المنتظمين بالقسم: `{active_students_count}` متدرب
🔹 نسبة الحضور الأسبوعية العامة: `{weekly_attendance_rate}%` 📈

📱 *معيار التحول الرقمي:*
🔹 المتدربين المسجلين بالبوت: `{users_count}` متدرب
🔹 السجلات المؤتمتة بالنظام: `{db_records}` سجل

📊 *معيار الأثر الفعلي:*
🔹 استفسارات عولجت بالذكاء الاصطناعي: `{ai_queries}` استفسار
🔹 إقرارات وتعهدات غياب نُفذت آلياً: `{pledges_count}` تعهد

⏳ *معيار الكفاءة التشغيلية:*
✅ توفير وقت الإدارة بمقدار: *{total_hours_saved} ساعة عمل!*

♻️ *معيار الاستدامة:*
✅ ربط سحابي وتحديث دائم (24/7).
"""
    await update.message.reply_text(report_msg, parse_mode='Markdown')

# --- 🌟 كشف الحالات الحرجة 🌟 ---
async def critical_cases_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID: return
    
    if not os.path.exists('data.xlsx'):
        return await update.message.reply_text("⚠️ لا يوجد ملف بيانات حالياً.")
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    try:
        df = pd.read_excel('data.xlsx', dtype=str)
        df['numeric_perc'] = pd.to_numeric(df['parsnt'].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        
        critical_df = df[df['numeric_perc'] >= 15].copy()
        critical_df = critical_df.sort_values(by='numeric_perc', ascending=False)
        
        if critical_df.empty:
            return await update.message.reply_text("✅ أبشرك، لا يوجد أي حالات حرمان أو إنذار حالياً.")
            
        msg = f"⚠️ *كشف المتدربين في مرحلة الخطر (15% فما فوق)*\n{SEP}\n"
        
        for _, row in critical_df.iterrows():
            perc = row['numeric_perc']
            status = "🔴 محروم" if perc >= 20 else "🟡 منذر"
            msg += f"👤 *{row['stu_nam']}*\n"
            msg += f"🔢 `{row['stu_num']}` | 📖 {row['c_nam']}\n"
            msg += f"📊 النسبة: *%{perc}* ({status})\n\n"
            
            if len(msg) > 3500:
                await update.message.reply_text(msg, parse_mode='Markdown')
                msg = ""
                
        if msg:
            await update.message.reply_text(msg, parse_mode='Markdown')
            
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في إعداد الكشف: {e}")

# --- 🌟 محرك معالجة الملفات للمدير (إكسل وتقارير) 🌟 ---
async def process_admin_excel(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    doc = update.message.document
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    status_msg = await update.message.reply_text("⏳ جاري تحليل الملف وفك التشفير...")
    
    try:
        file = await context.bot.get_file(doc.file_id)
        if doc.file_name.endswith('.csv'):
            temp_file = "temp_rayat.csv"
            await file.download_to_drive(temp_file)
            
            with open(temp_file, 'rb') as f: raw_bytes = f.read()
            best_enc = 'utf-8' 
            for enc in ['utf-8', 'utf-8-sig', 'windows-1256', 'cp1256', 'iso-8859-6']:
                try:
                    text = raw_bytes.decode(enc)
                    if 'المتدرب' in text or 'المقرر' in text or 'الغياب' in text or 'رقم' in text or 'نسبة التحضير' in text:
                        best_enc = enc; break 
                except: pass
                    
            df_raw = pd.read_csv(io.StringIO(raw_bytes.decode(best_enc)), dtype=str, sep=',', on_bad_lines='skip')
            
            is_quality_report = any('نسبة التحضير' in str(c) for c in df_raw.columns) and any('اسم المدرب' in str(c) for c in df_raw.columns)

            if is_quality_report:
                col_prep_percent = [c for c in df_raw.columns if 'نسبة التحضير' in str(c)][0]
                col_trainer_name = [c for c in df_raw.columns if 'اسم المدرب' in str(c)][0]
                col_total_prep = [c for c in df_raw.columns if 'إجمالي التحضير' in str(c)][0]
                col_present = [c for c in df_raw.columns if 'تحضير مسجل' in str(c)][0]

                df_raw[col_prep_percent] = pd.to_numeric(df_raw[col_prep_percent].astype(str).str.replace('%', '').str.strip(), errors='coerce').fillna(0)
                df_raw[col_total_prep] = pd.to_numeric(df_raw[col_total_prep], errors='coerce').fillna(0)
                df_raw[col_present] = pd.to_numeric(df_raw[col_present], errors='coerce').fillna(0)

                total_sections = len(df_raw)
                unrecorded_df = df_raw[df_raw[col_prep_percent] < 100]
                unrecorded_sections_count = len(unrecorded_df)
                recorded_sections_count = total_sections - unrecorded_sections_count

                total_trainers = df_raw[col_trainer_name].nunique()
                trainers_not_recorded = unrecorded_df[col_trainer_name].dropna().unique()
                unrecorded_trainers_count = len(trainers_not_recorded)
                recorded_trainers_count = total_trainers - unrecorded_trainers_count

                total_expected_hits = df_raw[col_total_prep].sum()
                total_present_hits = df_raw[col_present].sum()
                attendance_rate = round((total_present_hits / total_expected_hits) * 100, 2) if total_expected_hits > 0 else 0
                
                report_quality_msg = f"""
📑 *تقرير متابعة سير العملية التدريبية الأسبوعية* 📑
{SEP}
👥 *إحصائيات المتدربين والحضور:*
▫️ إجمالي المتدربين (التحضير): `{int(total_expected_hits)}`
▫️ المتدربين الحاضرين: `{int(total_present_hits)}`
📈 نسبة الحضور: `{attendance_rate}%`

📝 *إحصائيات الشعب التدريبية:*
▫️ إجمالي عدد الشعب: `{total_sections}`
✅ الشعب المحضرة: `{recorded_sections_count}`
⚠️ الشعب غير المحضرة: `{unrecorded_sections_count}`

👨‍🏫 *إحصائيات المدربين:*
▫️ إجمالي عدد المدربين: `{total_trainers}`
✅ المدربين المحضرين: `{recorded_trainers_count}`
⚠️ المدربين غير المحضرين: `{unrecorded_trainers_count}`
"""
                if unrecorded_sections_count > 0:
                    report_quality_msg += f"\n{SEP}\n📋 *المدربين المتأخرين بالرصد:*"
                    for trainer in trainers_not_recorded:
                        trainer_sections = unrecorded_df[unrecorded_df[col_trainer_name] == trainer]
                        sections_count = len(trainer_sections)
                        report_quality_msg += f"\n▫️ {trainer} `({sections_count} شعب)`"
                else:
                    report_quality_msg += f"\n{SEP}\n🎉 *عمل مميز! جميع الشعب مُحضرة بنسبة 100%.*"

                os.remove(temp_file)
                await status_msg.edit_text(report_quality_msg, parse_mode='Markdown')
                return
            
            df_clean = pd.DataFrame()
            col_map = {'c_course': -1, 'c_id': -1, 'c_name': -1, 'c_perc': -1, 'c_perc_no': -1, 'c_hrs': -1}
            for i, col in enumerate(df_raw.columns):
                clean_col = str(col).replace(' ', '').replace('أ', 'ا').replace('إ', 'ا').replace('"', '')
                if 'اسمالمقرر' in clean_col: col_map['c_course'] = i
                elif 'رقمالمتدرب' in clean_col: col_map['c_id'] = i
                elif 'اسمالمتدرب' in clean_col: col_map['c_name'] = i
                elif 'بعذروبدون' in clean_col and 'نسبه' in clean_col: col_map['c_perc'] = i
                elif 'بدونعذر' in clean_col and 'نسبه' in clean_col and 'بعذروبدون' not in clean_col: col_map['c_perc_no'] = i
                elif 'ساعات' in clean_col and 'بعذروبدون' in clean_col: col_map['c_hrs'] = i

            if col_map['c_course'] == -1: col_map['c_course'] = 14 if len(df_raw.columns) > 14 else 0
            if col_map['c_id'] == -1: col_map['c_id'] = 16 if len(df_raw.columns) > 16 else 0
            if col_map['c_name'] == -1: col_map['c_name'] = 17 if len(df_raw.columns) > 17 else 0
            if col_map['c_perc'] == -1: col_map['c_perc'] = 18 if len(df_raw.columns) > 18 else 0
            if col_map['c_perc_no'] == -1: col_map['c_perc_no'] = 22 if len(df_raw.columns) > 22 else -1
            if col_map['c_hrs'] == -1: col_map['c_hrs'] = 25 if len(df_raw.columns) > 25 else -1

            df_clean['c_nam'] = df_raw.iloc[:, col_map['c_course']].astype(str)
            df_clean['stu_num'] = df_raw.iloc[:, col_map['c_id']].astype(str)
            df_clean['stu_nam'] = df_raw.iloc[:, col_map['c_name']].astype(str)
            df_clean['parsnt'] = df_raw.iloc[:, col_map['c_perc']].astype(str)
            df_clean['parsnt_no'] = df_raw.iloc[:, col_map['c_perc_no']].astype(str) if col_map['c_perc_no'] != -1 else ""
            df_clean['hrs'] = df_raw.iloc[:, col_map['c_hrs']].astype(str) if col_map['c_hrs'] != -1 else ""
            
            df_clean['stu_num'] = df_clean['stu_num'].str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
            df_clean = df_clean[df_clean['stu_num'].str.len() >= 5] 
            for col in df_clean.columns: df_clean[col] = df_clean[col].replace('nan', '').str.strip()
                
            df_clean['day'] = datetime.now().strftime("%Y-%m-%d")
            df_clean.to_excel("data.xlsx", index=False)
            records_count = len(df_clean)
            
            records = df_clean.to_dict('records')
            if len(records) > 0 and db is not None:
                db["trainees_data"].delete_many({})
                db["trainees_data"].insert_many(records)

            os.remove(temp_file)
        else:
            await file.download_to_drive("data.xlsx")
            df_clean = pd.read_excel('data.xlsx')
            records_count = len(df_clean)
        
        github_status = backup_to_github("data.xlsx")
        await status_msg.edit_text(f"✅ *نجاح ساحق (تحديث قاعدة الطلاب)!*\n📊 *النتيجة:* حفظ `{records_count}` متدرب.\n🌐 *السحابة:* {github_status}", parse_mode='Markdown')
    except Exception as e:
        await status_msg.edit_text(f"⚠️ *فشل التحديث:* `{e}`", parse_mode='Markdown')
