import logging
import json
import os
import threading
from flask import Flask, render_template, jsonify, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, filters,
)
from pymongo import MongoClient

# লগিং সেটআপ
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# এনভায়রনমেন্ট ভেরিয়েবল থেকে টোকেন এবং ডাটাবেস লিংক নেওয়া
TOKEN = os.environ.get("BOT_TOKEN", "8713892015:AAFez0mngDbYsAxsl-aE0fQOJqnnvHh5_K8")
ADMIN_ID = 7100342395
BOT_USERNAME = "Fastpay8_bot"

# MongoDB কানেকশন সেটআপ
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://admin:Bashar904@cluster0.nkm8mxx.mongodb.net/?appName=Cluster0")
client = MongoClient(MONGO_URI)
db = client["telegram_bot_db"]
users_collection = db["users"]

pending_withdrawals = {}

# ডাটা ফেচ বা পাওয়ার ফাংশন
def get_user_data(user_id):
    user_data = users_collection.find_one({"user_id": user_id})
    if not user_data:
        user_data = {
            "user_id": user_id,
            "balance": 150.0,
            "referrals": [],
            "referred_by": None,  # এফিলিয়েটের জন্য কে কার মাধ্যমে এসেছে তা ট্র্যাক করতে
            "total_deposit": 0.0,
            "total_withdrawal": 0
        }
        users_collection.insert_one(user_data)
    return user_data

def update_user_field(user_id, update_data):
    users_collection.update_one({"user_id": user_id}, {"$set": update_data}, upsert=True)

# --- ফ্লাস্ক (Flask) ওয়েব সার্ভার সেটআপ (মিনি অ্যাপের জন্য) ---
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_balance/<int:user_id>')
def get_balance(user_id):
    user_data = get_user_data(user_id)
    return jsonify({"status": "success", "balance": user_data.get("balance", 150.0)})

@app.route('/update_balance', methods=['POST'])
def update_balance():
    try:
        data = request.get_json()
        user_id = int(data.get("user_id"))
        amount_diff = float(data.get("amount_diff"))
        
        user_data = get_user_data(user_id)
        current_balance = user_data.get("balance", 150.0)
        new_balance = current_balance + amount_diff
        
        if new_balance < 0:
            new_balance = 0.0
            
        update_user_field(user_id, {"balance": new_balance})
        
        return jsonify({"status": "success", "new_balance": new_balance})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# --- টেলিগ্রাম বট হ্যান্ডলার্স ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    user_data = users_collection.find_one({"user_id": user_id})
    is_new_user = False
    
    if not user_data:
        user_data = {
            "user_id": user_id,
            "balance": 150.0,
            "referrals": [],
            "referred_by": None,
            "total_deposit": 0.0,
            "total_withdrawal": 0
        }
        users_collection.insert_one(user_data)
        is_new_user = True
        
    if context.args and is_new_user:
        payload = context.args[0]
        if payload.startswith("ref_"):
            try:
                referrer_id = int(payload.split("_")[1])
                if referrer_id != user_id:
                    ref_user = get_user_data(referrer_id)
                    referrals_list = ref_user.get("referrals", [])
                    if user_id not in referrals_list:
                        referrals_list.append(user_id)
                        new_ref_balance = ref_user.get("balance", 0.0) + 100.0
                        
                        # রেফারার সেভ করা এবং যার মাধ্যমে এসেছে তাকে রেকর্ড করা
                        update_user_field(referrer_id, {
                            "referrals": referrals_list,
                            "balance": new_ref_balance
                        })
                        update_user_field(user_id, {"referred_by": referrer_id})
                        
                        await context.bot.send_message(
                            referrer_id, 
                            "🎉 অভিনন্দন! আপনার রেফারল লিংকে নতুন একজন ইউজার যুক্ত হয়েছে এবং আপনি রেফার বোনাস হিসেবে ১০০ টাকা পেয়েছেন!"
                        )
            except ValueError:
                pass
    
    web_app_url = "https://telegram-bot-oh28.onrender.com"
    
    keyboard_inline = [
        [InlineKeyboardButton("🎮 গেম খেলুন (Mini App)", web_app={"url": web_app_url})]
    ]
    reply_markup_inline = InlineKeyboardMarkup(keyboard_inline)
    
    keyboard = [
        ["👤 প্রোফাইল", "💰 ব্যালেন্স"],
        ["📥 জমা", "📤 উত্তোলন"],
        ["🔗 রেফার লিংক"]
    ]
    
    await update.message.reply_text(
        f"স্বাগতম, {user.first_name}! ওয়েলকাম বোনাস হিসেবে আপনি পেয়েছেন ১৫০ টাকা। অপশন বেছে নিন:", 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    
    await update.message.reply_text(
        "👇 নিচে গেম খেলে আয় করতে বাটনে ক্লিক করুন:", 
        reply_markup=reply_markup_inline
    )

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    parts = text.replace("/deposit", "").strip().split()
    
    if len(parts) < 2:
        await update.message.reply_text("সঠিক নিয়ম: /deposit <পরিমাণ> <TrxID>\nউদাহরণ: /deposit 200 ABC123XYZ")
        return
        
    amount_str, trx = parts[0], parts[1]
    
    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ জমার পরিমাণ অবশ্যই সঠিক সংখ্যা হতে হবে। সঠিক নিয়ম: /deposit 200 TrxID")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"dep_approve_{user.id}_{amount}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{user.id}_{amount}")
        ]
    ]
    try:
        await context.bot.send_message(
            ADMIN_ID, 
            f"📥 নতুন জমা রিকোয়েস্ট!\n👤 ইউজার: {user.first_name}\n💰 পরিমাণ: {amount}\n🆔 TrxID: {trx}", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.message.reply_text("✅ আপনার জমা রিকোয়েস্ট অ্যাডমিনের কাছে পাঠানো হয়েছে।")
    except Exception as e:
        await update.message.reply_text("❌ দুঃখিত, রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে।")

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    parts = text.replace("/withdraw", "").strip().split()
    
    if len(parts) < 2:
        await update.message.reply_text("সঠিক নিয়ম: /withdraw <নম্বর> <পরিমাণ>\nউদাহরণ: /withdraw 017 1200")
        return
        
    try:
        phone = parts[0]
        amount = float(parts[1])
    except ValueError:
        await update.message.reply_text("❌ ভুল ফরম্যাট! সঠিক নিয়মে লিখুন: /withdraw <নম্বর> <পরিমাণ>\nউদাহরণ: /withdraw 017 1200")
        return

    if amount < 1200:
        await update.message.reply_text("❌ মিনিমাম উত্তোলন ১২০০ টাকা।")
        return
        
    user_data = get_user_data(user.id)
    current_balance = user_data.get("balance", 0.0)
    
    # শর্ত ১: পর্যাপ্ত ব্যালেন্স চেক
    if current_balance < amount:
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
        error_msg = f"❌ আপনার পর্যাপ্ত পরিমাণে টাকা নাই!\n🔗 বেশি বেশি রেফার করে আয় করুন:\n{ref_link}"
        await update.message.reply_text(error_msg)
        return

    # শর্ত ২: ন্যূনতম ২ টি রেফার চেক
    referrals_list = user_data.get("referrals", [])
    if len(referrals_list) < 2:
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
        ref_error_msg = (
            "❌ টাকা উত্তোলন করতে হলে আপনার অ্যাকাউন্টে কমপক্ষে **২ টি সফল রেফার (Referral)** থাকতে হবে!\n\n"
            f"👥 আপনার বর্তমান রেফার: {len(referrals_list)} জন\n\n"
            f"🔗 আপনার রেফারেল লিংক:\n{ref_link}"
        )
        await update.message.reply_text(ref_error_msg)
        return

    # শর্ত ৩: ন্যূনতম ৫০০ টাকা ডিপোজিট চেক
    total_dep = user_data.get("total_deposit", 0.0)
    if total_dep < 500:
        deposit_msg = (
            "❌ টাকা উত্তোলন করতে হলে আপনার অ্যাকাউন্টে কমপক্ষে **৫০০ টাকা জমা (Deposit)** করতে হবে!\n\n"
            "📥 টাকা জমা করার নিয়ম:\n"
            "আমাদের বিকাশ (Merchant) পেমেন্ট নম্বর: `01919130118`\n"
            "টাকা পাঠিয়ে নিচের নিয়মে সেন্ড করুন:\n"
            "/deposit <পরিমাণ> <ট্রানজেকশন_আইডি>\n"
            "উদাহরণ: /deposit 500 ABC123XYZ"
        )
        await update.message.reply_text(deposit_msg)
        return

    # সব শর্ত পূরণ হলে উইথড্র মাধ্যম সিলেক্ট করার অপশন দেওয়া
    pending_withdrawals[user.id] = {"phone": phone, "amount": amount}
    
    keyboard = [
        [
            InlineKeyboardButton("🔴 বিকাশ (Bkash)", callback_data=f"method_bkash_{user.id}"),
            InlineKeyboardButton("🟠 নগদ (Nagad)", callback_data=f"method_nagad_{user.id}")
        ]
    ]
    await update.message.reply_text("📲 আপনি কোন মাধ্যমে টাকা নিতে চান তা নিচে থেকে সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    user = update.effective_user
    user_data = get_user_data(user.id)
    
    if "প্রোফাইল" in text:
        refs_count = len(user_data.get("referrals", []))
        total_dep = user_data.get("total_deposit", 0.0)
        profile_text = (
            f"👤 প্রোফাইল\n"
            f"🆔 আইডি: {user.id}\n"
            f"💰 ব্যালেন্স: {user_data.get('balance', 150.0)} টাকা\n"
            f"📥 মোট জমা: {total_dep} টাকা\n"
            f"👥 মোট রেফার: {refs_count} জন"
        )
        await update.message.reply_text(profile_text)
        
    elif "ব্যালেন্স" in text:
        await update.message.reply_text(f"💰 বর্তমান ব্যালেন্স: {user_data.get('balance', 150.0)} টাকা")
        
    elif "জমা" in text:
        deposit_msg = (
            "📥 টাকা জমা করার নিয়ম:\n\n"
            "আমাদের বিকাশ (Merchant) পেমেন্ট নম্বর: `01919130118`\n"
            "(একাউন্টটি মার্চেন্ট)\n\n"
            "এই নাম্বারে টাকা পাঠিয়ে নিচে দেওয়া নিয়মে সেন্ড করুন:\n"
            "/deposit <পরিমাণ> <ট্রানজেকশন_আইডি>\n\n"
            "উদাহরণ: /deposit 200 ABC123XYZ"
        )
        await update.message.reply_text(deposit_msg)
        
    elif "উত্তোলন" in text:
        await update.message.reply_text(
            "উত্তোলন করতে এই নিয়মে লিখুন:\n"
            "/withdraw <নম্বর> <পরিমাণ>\n"
            "উদাহরণ: /withdraw 017 1200"
        )
        
    elif "রেফার" in text or "লিংক" in text:
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
        refs_count = len(user_data.get("referrals", []))
        ref_msg = (
            f"🔗 আপনার রেফারেল লিংক:\n{ref_link}\n\n"
            f"🎁 প্রতি সফল রেফারে পাবেন ১০০ টাকা বোনাস এবং আপনার রেফার করা কেউ ডিপোজিট করলে পাবেন **১০% এফিলিয়েট কমিশন**!\n"
            f"👥 আপনার মোট রেফার: {refs_count} জন"
        )
        await update.message.reply_text(ref_msg)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_parts = query.data.split("_")
    
    if data_parts[0] == "method":
        method = data_parts[1].capitalize()
        target_id = int(data_parts[2])
        
        if target_id not in pending_withdrawals:
            await query.edit_message_text("❌ সময়সীমা শেষ অথবা রিকোয়েস্ট পাওয়া যায়নি। আবার চেষ্টা করুন।")
            return
            
        wit_data = pending_withdrawals.pop(target_id)
        phone = wit_data["phone"]
        amount = wit_data["amount"]
        
        try:
            user_chat = await context.bot.get_chat(target_id)
            user_name = user_chat.first_name
        except:
            user_name = "User"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"wit_approve_{target_id}_{amount}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"wit_reject_{target_id}_{amount}")
            ]
        ]
        await context.bot.send_message(
            ADMIN_ID, 
            f"📤 নতুন উত্তোলন রিকোয়েস্ট!\n👤 ইউজার: {user_name}\n💳 মাধ্যম: {method}\n📞 নম্বর: {phone}\n💰 পরিমাণ: {amount}", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.edit_message_text(f"✅ আপনার উত্তোলনের মাধ্যম ({method}) সিলেক্ট হয়েছে এবং রিকোয়েস্ট অ্যাডমিনের কাছে পাঠানো হয়েছে।")
        return

    action_type = data_parts[0]
    status = data_parts[1]
    target_id = int(data_parts[2])
    amount = float(data_parts[3])
    
    user_data = get_user_data(target_id)
    
    if action_type == "dep":
        if status == "approve":
            new_bal = user_data.get("balance", 150.0) + amount
            new_dep = user_data.get("total_deposit", 0.0) + amount
            update_user_field(target_id, {"balance": new_bal, "total_deposit": new_dep})
            
            # --- এফিলিয়েট কমিশন (১০%) লজিক ---
            referrer_id = user_data.get("referred_by")
            if referrer_id:
                commission = amount * 0.10  # জমার ওপর ১০% কমিশন
                ref_user_data = get_user_data(referrer_id)
                ref_new_bal = ref_user_data.get("balance", 0.0) + commission
                
                # রেফারারের ব্যালেন্স আপডেট করা
                update_user_field(referrer_id, {"balance": ref_new_bal})
                
                # রেফারারকে নোটিফিকেশন পাঠানো
                try:
                    await context.bot.send_message(
                        referrer_id, 
                        f"🤝 অভিনন্দন! আপনার এফিলিয়েট ইউজার ডিপোজিট করার কারণে আপনি ১০% কমিশন অর্থাৎ **{commission} টাকা** বোনাস পেয়েছেন!"
                    )
                except Exception:
                    pass
            # -----------------------------------
            
            await query.edit_message_text(f"✅ জমা এপ্রুভ করা হয়েছে। (ইউজার: {target_id}, মোট জমা: {new_dep} টাকা)")
            await context.bot.send_message(target_id, f"🎉 অভিনন্দন! আপনার {amount} টাকা জমা এপ্রুভ হয়েছে। (আপনার মোট জমা: {new_dep} টাকা)")
        else:
            await query.edit_message_text("❌ জমা রিজেক্ট করা হয়েছে।")
            await context.bot.send_message(target_id, f"❌ দুঃখিত, আপনার {amount} টাকা জমার রিকোয়েস্টটি বাতিল করা হয়েছে।")
            
    elif action_type == "wit":
        if status == "approve":
            new_bal = max(0.0, user_data.get("balance", 150.0) - amount)
            new_wit = user_data.get("total_withdrawal", 0) + 1
            update_user_field(target_id, {"balance": new_bal, "total_withdrawal": new_wit})
            
            await query.edit_message_text(f"✅ উত্তোলন এপ্রুভ করা হয়েছে। (ইউজার: {target_id})")
            await context.bot.send_message(target_id, f"✅ আপনার {amount} টাকা উত্তোলন সফল হয়েছে এবং পেমেন্ট দেওয়া হয়েছে!")
        else:
            await query.edit_message_text("❌ উত্তোলন রিজেক্ট করা হয়েছে।")
            await context.bot.send_message(target_id, f"❌ দুঃখিত, আপনার {amount} টাকা উত্তোলনের রিকোয়েস্টটি রিজেক্ট করা হয়েছে।")

def main():
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    app_bot = ApplicationBuilder().token(TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("deposit", deposit_command))
    app_bot.add_handler(CommandHandler("withdraw", withdraw_command))
    app_bot.add_handler(CallbackQueryHandler(button_click))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_request))
    
    print("বট এবং ফ্লাস্ক সার্ভার সফলভাবে MongoDB ডাটাবেস সহ চালু হয়েছে...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
