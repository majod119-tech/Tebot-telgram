# ==========================================
# 📊 محرك التقارير الأسبوعية (المُحسن للملفات الجديدة)
# ==========================================
def build_weekly_report():
    try:
        if not os.path.exists("so09.csv"): 
            return "⚠️ لم يتم رفع إحصائيات الشعب (SO09) حتى الآن."
        
        df = pd.read_csv("so09.csv", dtype=str)
        
        # الاعتماد على الأسماء الدقيقة من ملفك
        col_prep = 'نسبة التحضير'
        col_trainer = 'اسم المدرب'
        col_section = 'رمز المقرر'
        col_deprived = 'عدد المحرومين'
        col_total_stu = 'إجمالي المتدربين'

        if col_prep not in df.columns or col_trainer not in df.columns:
            return "⚠️ أعمدة التقرير غير متطابقة مع نموذج نظام رايات المعتمد."

        # تنظيف وتحويل الأرقام
        df[col_prep] = pd.to_numeric(df[col_prep].astype(str).str.replace('%', ''), errors='coerce').fillna(0)
        df[col_deprived] = pd.to_numeric(df[col_deprived], errors='coerce').fillna(0)
        df[col_total_stu] = pd.to_numeric(df[col_total_stu], errors='coerce').fillna(0)
        
        total_sections = len(df)
        prepared_sections = len(df[df[col_prep] >= 100])
        unprepared_sections = total_sections - prepared_sections
        
        total_deprived = int(df[col_deprived].sum())
        
        # إحصائيات المدربين
        trainers_df = df.groupby(col_trainer).agg(
            total_sec=(col_section, 'count'),
            prep_sec=(col_prep, lambda x: (x >= 100).sum())
        ).reset_index()
        
        total_trainers = len(trainers_df)
        fully_prepared_trainers = len(trainers_df[trainers_df['total_sec'] == trainers_df['prep_sec']])
        late_trainers_df = trainers_df[trainers_df['total_sec'] > trainers_df['prep_sec']]
        late_trainers = len(late_trainers_df)
        
        late_list_text = "\n".join([f"▫️ {row[col_trainer]} ({int(row['total_sec'] - row['prep_sec'])} شعب)" for _, row in late_trainers_df.iterrows()])
        if not late_list_text: late_list_text = "لا يوجد تأخير، جميع المدربين أتموا الرصد ✅"
        
        # تطبيق معادلة الجودة لحساب الحضور 
        avg_attendance_perc = df[col_prep].mean()
        
        # جلب إجمالي المتدربين من الإكسل الأساسي
        df_students = get_excel_data()
        total_trainees = df_students['stu_num'].nunique() if df_students is not None else int(df[col_total_stu].sum())
        present_trainees = int((avg_attendance_perc / 100) * total_trainees) if total_trainees > 0 else 0

        report = f"""
📑 *تقرير متابعة سير العملية التدريبية الأسبوعية* 📑
{SEP}

👥 *إحصائيات المتدربين والحضور:*
▫️ إجمالي المتدربين (التحضير): `{total_trainees}`
▫️ المتدربين الحاضرين: `{present_trainees}`
📈 نسبة الحضور: `{avg_attendance_perc:.2f}%`
🛑 المتدربين المحرومين هذا الأسبوع: `{total_deprived}`

📝 *إحصائيات الشعب التدريبية:*
▫️ إجمالي عدد الشعب: `{total_sections}`
✅ الشعب المحضرة: `{prepared_sections}`
⚠️ الشعب غير المحضرة: `{unprepared_sections}`

👨‍🏫 *إحصائيات المدربين:*
▫️ إجمالي عدد المدربين: `{total_trainers}`
✅ المدربين المحضرين: `{fully_prepared_trainers}`
⚠️ المدربين غير المحضرين: `{late_trainers}`
{SEP}
📋 *المدربين المتأخرين بالرصد:*
{late_list_text}
"""
        return report
    except Exception as e:
        return f"⚠️ خطأ في المعالجة: {e}"

# ==========================================
# 7. محرك رفع الملفات وصور الأعذار (المُحدث للتعرف الآلي)
# ==========================================
async def handle_docs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private': return 
    user_id = str(update.effective_user.id)
    
    # معالجة ملفات الإدارة (رايات)
    if user_id == ADMIN_ID and update.message.document and update.message.document.file_name.endswith(('.xlsx', '.xls', '.csv')):
        status_msg = await update.message.reply_text("⏳ جاري تحليل وتصنيف التقرير المرفوع تلقائياً...")
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            temp_file = "temp_rayat.csv" if update.message.document.file_name.endswith('.csv') else "data.xlsx"
            await file.download_to_drive(temp_file)
            
            if temp_file.endswith('.csv'):
                with open(temp_file, 'rb') as f: raw_bytes = f.read()
                best_enc = 'utf-8'
                for enc in ['utf-8', 'windows-1256', 'cp1256']:
                    try: text = raw_bytes.decode(enc); best_enc = enc; break
                    except: pass
                
                df_raw = pd.read_csv(io.StringIO(raw_bytes.decode(best_enc)), dtype=str, sep=',', on_bad_lines='skip')
                
                # 🟢 التعرف على ملف إحصائيات الشعب (SO09)
                if 'اسم المدرب' in df_raw.columns and 'نسبة التحضير' in df_raw.columns:
                    df_raw.to_csv("so09.csv", index=False)
                    os.remove(temp_file)
                    report_text = build_weekly_report()
                    
                    # حفظ التقرير في قاعدة البيانات (أرشفة أسبوعية)
                    reports_col.insert_one({
                        "type": "SO09",
                        "date": datetime.now(),
                        "total_sections": len(df_raw),
                        "report_summary": report_text
                    })
                    
                    return await status_msg.edit_text(report_text, parse_mode='Markdown')

                # 🟢 التعرف على ملف غياب المتدربين (السجل الأساسي)
                elif 'اسم المتدرب' in df_raw.columns and 'رقم المتدرب' in df_raw.columns and 'إجمالي نسبة الغياب بعذر وبدون عذر' in df_raw.columns:
                    df_clean = pd.DataFrame()
                    df_clean['c_nam'] = df_raw['اسم المقرر'].astype(str)
                    df_clean['stu_num'] = df_raw['رقم المتدرب'].astype(str).str.replace(r'\.0$', '', regex=True).str.replace(r'\D', '', regex=True)
                    df_clean['stu_nam'] = df_raw['اسم المتدرب'].astype(str)
                    df_clean['parsnt'] = df_raw['إجمالي نسبة الغياب بعذر وبدون عذر'].astype(str)
                    
                    df_clean = df_clean[df_clean['stu_num'].str.len() >= 5]
                    df_clean.to_excel("data.xlsx", index=False)
                    os.remove(temp_file)
                    
                    global EXCEL_CACHE
                    EXCEL_CACHE = None 
                    
                    # حفظ أرشفة التحديث في قاعدة البيانات
                    reports_col.insert_one({
                        "type": "Trainees_Absence",
                        "date": datetime.now(),
                        "total_records": len(df_clean)
                    })
                    
                    return await status_msg.edit_text(f"✅ *تم تحديث قاعدة بيانات حضور الطلاب بنجاح!*\nتم رفع وتوثيق {len(df_clean)} سجل في الأرشيف للمقارنات المستقبلية.", parse_mode='Markdown')
                
                else:
                    os.remove(temp_file)
                    return await status_msg.edit_text("⚠️ لم يتعرف النظام على نوع الملف. يرجى التأكد من استخراج التقارير الصحيحة من رايات.")

        except Exception as e: 
            await status_msg.edit_text(f"⚠️ فشل التحديث: {e}")
        return

    # 🟢 حفظ الأعذار الطبية في قاعدة البيانات 🟢
    if update.message.photo or update.message.document:
        caption_text = update.message.caption
        stu_id = ''.join(filter(str.isdigit, str(caption_text))) if caption_text else ""
        
        if not caption_text or len(stu_id) < 5:
            return await update.message.reply_text("🛑 *مرفوض!* ارفق الصورة واكتب *رقمك التدريبي* في الوصف.", parse_mode='Markdown')
            
        await context.bot.send_chat_action(chat_id=user_id, action=ChatAction.UPLOAD_PHOTO)
        status_msg = await update.message.reply_text("⏳ جاري توثيق العذر في قاعدة بيانات القسم...")
        
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
            
            excuses_col.insert_one({
                "telegram_id": user_id,
                "stu_num": stu_id,
                "date": timestamp,
                "file_id": file_id,
                "status": "مستلم"
            })

            await context.bot.send_photo(chat_id=GROUP_ID, photo=file_id, caption=f"📥 *عذر جديد مُوثق:*\nرقم المتدرب: {stu_id}\n⏱️ وقت الرفع: {timestamp}", parse_mode='Markdown')
                
            if user_id in user_states: del user_states[user_id]
            await status_msg.edit_text("✅ *تم الحفظ في قاعدة البيانات وإرسال العذر للإدارة بنجاح.*", parse_mode='Markdown')
            await update.message.reply_text("العودة 🏠", reply_markup=get_main_menu())
        except Exception as e: 
            await status_msg.edit_text(f"⚠️ خطأ أثناء المعالجة.")
