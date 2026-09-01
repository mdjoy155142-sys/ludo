async def add_custom_bonus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    # কমান্ডের সাথে অ্যামাউন্ট চেক করা (যেমন: /addcustombonus 500)
    if not context.args:
        await update.message.reply_text("❌ সঠিক নিয়মে লিখুন:\n`/addcustombonus <টাকার পরিমাণ>`\nউদাহরণ: `/addcustombonus 500`", parse_mode="Markdown")
        return

    try:
        bonus_amount = float(context.args[0])
        if bonus_amount <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ দয়া করে সঠিক সংখ্যা লিখুন। যেমন: `/addcustombonus 200`", parse_mode="Markdown")
        return

    try:
        all_users = list(users_collection.find())
        success_count = 0

        await update.message.reply_text(f"⏳ সকল ইউজারের ব্যালেন্সে {bonus_amount} টাকা করে যোগ করা হচ্ছে...")

        for u in all_users:
            target_user_id = u.get("user_id")
            current_bal = u.get("balance", 0.0)
            new_bal = round(current_bal + bonus_amount, 2)
            
            users_collection.update_one({"user_id": target_user_id}, {"$set": {"balance": new_bal}})
            success_count += 1

            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎁 **স্পেশাল উপহার বা বোনাস!**\n\nঅফিসিয়াল ঘোষণা অনুযায়ী আপনার অ্যাকাউন্টে সফলভাবে **{bonus_amount} টাকা বোনাস** যোগ করা হয়েছে! 💰\n\nএখনই গেম খেলে ইনকাম করুন।",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        await update.message.reply_text(f"✅ সফলভাবে মোট {success_count} জন ইউজারের ব্যালেন্সে {bonus_amount} টাকা করে যোগ করা হয়েছে!")
    except Exception as e:
        await update.message.reply_text(f"❌ সমস্যা হয়েছে: {str(e)}")
