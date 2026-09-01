from datetime import datetime, timedelta, timezone
import logging
import os
from pymongo import MongoClient
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# লগিং সেটআপ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# এনভায়রনমেন্ট ভেরিয়েবল বা টোকেন
TOKEN = os.environ.get(
    "BOT_TOKEN", "8713892015:AAFez0mngDbYsAxsl-aE0fQOJqnnvHh5_K8"
)
ADMIN_ID = 7100342395
BOT_USERNAME = "Fastpay8_bot"
SUPPORT_USERNAME = "Jou904"
EXCHANGE_RATE = 126.0

# MongoDB কানেকশন
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://admin:Bashar904@cluster0.nkm8mxx.mongodb.net/?appName=Cluster0",
)
client = MongoClient(MONGO_URI)
db = client["telegram_bot_db"]
users_collection = db["users"]

pending_withdrawals = {}


def get_user_data(user_id):
  user_data = users_collection.find_one({"user_id": user_id})
  if not user_data:
    user_data = {
        "user_id": user_id,
        "balance": 150.0,
        "referrals": [],
        "referred_by": None,
        "total_deposit": 0.0,
        "total_withdrawal": 0,
        "last_task_date": None,
        "task_streak": 0,
        "task_cycle_start": None,
        "bonus_claimed": False,
    }
    users_collection.insert_one(user_data)
  return user_data


def update_user_field(user_id, update_data):
  users_collection.update_one(
      {"user_id": user_id}, {"$set": update_data}, upsert=True
  )


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
        "total_withdrawal": 0,
        "last_task_date": None,
        "task_streak": 0,
        "task_cycle_start": None,
        "bonus_claimed": False,
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
            new_ref_balance = round(ref_user.get("balance", 0.0) + 100.0, 2)
            update_user_field(
                referrer_id,
                {"referrals": referrals_list, "balance": new_ref_balance},
            )
            update_user_field(user_id, {"referred_by": referrer_id})
            await context.bot.send_message(
                referrer_id,
                "🎉 অভিনন্দন! আপনার রেফারল লিংকে নতুন একজন ইউজার যুক্ত হয়েছে"
                " এবং আপনি রেফার বোনাস হিসেবে ১০০ টাকা পেয়েছেন!",
            )
      except ValueError:
        pass

  support_url = f"https://t.me/{SUPPORT_USERNAME}"
  keyboard_inline = [
      [InlineKeyboardButton("👨‍💻 লাইভ সাপোর্ট (Live Support)", url=support_url)]
  ]
  current_balance = round(user_data.get("balance", 150.0), 2)
  reply_markup_inline = InlineKeyboardMarkup(keyboard_inline)

  keyboard = [
      ["👤 প্রোফাইল", "💰 ব্যালেন্স"],
      ["📥 জমা", "📤 উত্তোলন"],
      ["🔗 রেফার লিংক", "🎁 ডেইলি টাস্ক"],
      ["🆘 লাইভ সাপোর্ট"],
  ]

  await update.message.reply_text(
      f"স্বাগতম, {user.first_name}! আপনার বর্তমান ব্যালেন্স {current_balance}"
      " টাকা। অপশন বেছে নিন:",
      reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
  )
  await update.message.reply_text(
      "👇 সাপোর্টে কথা বলতে নিচে বাটন সিলেক্ট করুন:",
      reply_markup=reply_markup_inline,
  )


async def binance_deposit_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  user = update.effective_user
  text = update.message.text
  parts = text.replace("/binancedeposit", "").strip().split()

  if len(parts) < 2:
    await update.message.reply_text(
        f"সঠিক নিয়ম: /binancedeposit <ইউএসডিটি_পরিমাণ> <Binance_Pay_ID>\nউদাহরণ:"
        f" /binancedeposit 10 562714210\n💱 রেট: ১ ডলার = {EXCHANGE_RATE} টাকা"
    )
    return

  amount_str, binance_pay_id = parts[0], parts[1]
  try:
    usd_amount = float(amount_str)
    if usd_amount <= 0:
      raise ValueError()
  except ValueError:
    await update.message.reply_text(
        "❌ জমার পরিমাণ সঠিক সংখ্যা হতে হবে। উদাহরণ: /binancedeposit 10"
        " 562714210"
    )
    return

  bdt_amount = int(
      round(usd_amount * EXCHANGE_RATE)
  )  // ইন্টিজার করা হলো সেফটির জন্য

  keyboard = [
      [
          InlineKeyboardButton(
              "✅ Approve",
              callback_data=f"dep_approve_{user.id}_{bdt_amount}",
          ),
          InlineKeyboardButton(
              "❌ Reject", callback_data=f"dep_reject_{user.id}_{bdt_amount}"
          ),
      ]
  ]
  try:
    await context.bot.send_message(
        ADMIN_ID,
        f"📥 নতুন বাইনান্স পে জমা রিকোয়েস্ট!\n👤 ইউজার: {user.first_name} (ID:"
        f" {user.id})\n💵 ইউএসডিটি: ${usd_amount}\n💰 বিডিটি পরিমাণ: {bdt_amount}"
        f" টাকা\n🆔 Binance Pay ID: `{binance_pay_id}`\n💱 রেট: ১$ ="
        f" {EXCHANGE_RATE}৳",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    await update.message.reply_text(
        "✅ আপনার বাইনান্স পে জমা রিকোয়েস্ট অ্যাডমিনের কাছে পাঠানো হয়েছে।"
    )
  except Exception:
    await update.message.reply_text("❌ দুঃখিত, রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে।")


async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  text = update.message.text
  parts = text.replace("/withdraw", "").strip().split()

  if len(parts) < 2:
    await update.message.reply_text(
        f"সঠিক নিয়ম: /withdraw <বাইনান্স পে আইডি> <পরিমাণ (টাকায়)>\nউদাহরণ:"
        f" /withdraw 562714210 1200\n💱 রেট: ১ ডলার = {EXCHANGE_RATE} টাকা"
    )
    return

  try:
    pay_id = parts[0]
    amount = float(parts[1])
  except ValueError:
    await update.message.reply_text(
        "❌ ভুল ফরম্যাট! সঠিক নিয়মে লিখুন: /withdraw <বাইনান্স পে আইডি> <পরিমাণ>"
    )
    return

  if amount < 1200:
    await update.message.reply_text("❌ মিনিমাম উত্তোলন ১২০০ টাকা।")
    return

  user_data = get_user_data(user.id)
  current_balance = user_data.get("balance", 0.0)

  if current_balance < amount:
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
    await update.message.reply_text(
        f"❌ আপনার পর্যাপ্ত পরিমাণে টাকা নাই!\n🔗 বেশি বেশি রেফার করুন:\n{ref_link}"
    )
    return

  referrals_list = user_data.get("referrals", [])
  if len(referrals_list) < 2:
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
    await update.message.reply_text(
        "❌ উত্তোলন করতে হলে কমপক্ষে **২ টি সফল রেফার** থাকতে হবে!\n👥 বর্তমান"
        f" রেফার: {len(referrals_list)} জন\n🔗 লিংক:\n{ref_link}"
    )
    return

  total_dep = user_data.get("total_deposit", 0.0)
  if total_dep < 200:
    await update.message.reply_text(
        "❌ উত্তোলন করতে হলে কমপক্ষে **২০০ টাকা জমা** করতে হবে!"
    )
    return

  pending_withdrawals[user.id] = {"pay_id": pay_id, "amount": amount}
  keyboard = [
      [
          InlineKeyboardButton(
              "🟡 বাইনান্স পে (Binance Pay)",
              callback_data=f"method_binance_{user.id}",
          )
      ]
  ]
  await update.message.reply_text(
      "📲 পেমেন্ট মাধ্যম সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard)
  )


async def handle_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if not update.message or not update.message.text:
    return
  text = update.message.text.strip()
  user = update.effective_user

  user_data = get_user_data(user.id)

  if "প্রোফাইল" in text:
    refs_count = len(user_data.get("referrals", []))
    total_dep = round(user_data.get("total_deposit", 0.0), 2)
    bal = round(user_data.get("balance", 150.0), 2)
    profile_text = (
        f"👤 প্রোফাইল\n🆔 আইডি: {user.id}\n💰 ব্যালেন্স: {bal} টাকা\n📥 মোট জমা:"
        f" {total_dep} টাকা\n👥 মোট রেফার: {refs_count} জন\n💱 রেট: ১$ ="
        f" {EXCHANGE_RATE}৳"
    )
    await update.message.reply_text(profile_text)
  elif "ব্যালেন্স" in text:
    bal = round(user_data.get("balance", 150.0), 2)
    dollar_val = round(bal / EXCHANGE_RATE, 2)
    await update.message.reply_text(
        f"💰 বর্তমান ব্যালেন্স: {bal} টাকা (প্রায় ${dollar_val} USD)\n💱 রেট: ১"
        f" ডলার = {EXCHANGE_RATE} টাকা"
    )
  elif "জমা" in text:
    await update.message.reply_text(
        "📥 বাইনান্স পে (Binance Pay) এর মাধ্যমে জমা করুন:\n\n🟡 বাইনান্স পে আইডি"
        f" (Pay ID): `562714210`\n💱 এক্সচেঞ্জ রেট: ১ ডলার = {EXCHANGE_RATE}"
        " টাকা\n\nনিয়ম: /binancedeposit <ইউএসডিটি_পরিমাণ> <Binance_Pay_ID>",
        parse_mode="Markdown",
    )
  elif "উত্তোলন" in text:
    await update.message.reply_text(
        f"উত্তোলন নিয়ম: /withdraw <বাইনান্স পে আইডি> <পরিমাণ>\n💱 রেট: ১ ডলার ="
        f" {EXCHANGE_RATE} টাকা"
    )
  elif "রেফার" in text or "লিংক" in text:
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user.id}"
    await update.message.reply_text(
        f"🔗 আপনার রেফারেল লিংক:\n{ref_link}\n🎁 রেফারে পাবেন ১০০ টাকা বোনাস!"
    )
  elif "ডেইলি টাস্ক" in text:
    now = datetime.now(timezone.utc)
    last_date = user_data.get("last_task_date")
    streak = user_data.get("task_streak", 0)
    cycle_start = user_data.get("task_cycle_start")

    if cycle_start:
      if isinstance(cycle_start, str):
        try:
          cycle_start = datetime.fromisoformat(cycle_start)
        except ValueError:
          cycle_start = now
      if cycle_start.tzinfo is None:
        cycle_start = cycle_start.replace(tzinfo=timezone.utc)
      if now - cycle_start > timedelta(days=7):
        streak, cycle_start = 0, now
    else:
      cycle_start = now

    if last_date:
      if isinstance(last_date, str):
        try:
          last_date = datetime.fromisoformat(last_date)
        except ValueError:
          last_date = now
      if last_date.tzinfo is None:
        last_date = last_date.replace(tzinfo=timezone.utc)
      if now - last_date < timedelta(hours=24):
        time_left = timedelta(hours=24) - (now - last_date)
        hours, remainder = divmod(int(time_left.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        await update.message.reply_text(
            f"⏳ আজকের টাস্ক সম্পন্ন হয়েছে! অপেক্ষা করুন: {hours} ঘণ্টা {minutes}"
            " মিনিট।"
        )
        return

    if streak >= 7:
      streak, cycle_start = 0, now
    streak += 1
    reward = 30.0 if streak == 7 else 20.0
    new_balance = round(user_data.get("balance", 150.0) + reward, 2)

    update_user_field(
        user.id,
        {
            "balance": new_balance,
            "task_streak": streak,
            "last_task_date": now.isoformat(),
            "task_cycle_start": (
                cycle_start.isoformat()
                if isinstance(cycle_start, datetime)
                else cycle_start
            ),
        },
    )
    await update.message.reply_text(
        f"🎁 ডেইলি টাস্ক সম্পন্ন! বোনাস: **{reward} টাকা** (দিন {streak}/7)",
        parse_mode="Markdown",
    )
  elif "সাপোর্ট" in text or "Support" in text:
    await update.message.reply_text(
        f"🆘 লাইভ সাপোর্ট: 👨‍💻 @{SUPPORT_USERNAME}"
    )


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  # শুধু অ্যাডমিন বা ভ্যালিড ইউজার চেক করার জন্য (প্রয়োজনীয় সিকিউরিটি)
  if query.from_user.id != ADMIN_ID and not query.data.startswith("method_"):
    await query.answer(
        "❌ এই কাজটি করার অনুমতি আপনার নেই!", show_alert=True
    )
    return

  data_parts = query.data.split("_")

  if data_parts[0] == "method":
    target_id = int(data_parts[2])
    if target_id not in pending_withdrawals:
      await query.edit_message_text("❌ সময়সীমা শেষ।")
      return
    wit_data = pending_withdrawals.pop(target_id)
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"wit_approve_{target_id}_{int(wit_data['amount'])}",
            ),
            InlineKeyboardButton(
                "❌ Reject",
                callback_data=f"wit_reject_{target_id}_{int(wit_data['amount'])}",
            ),
        ]
    ]
    await context.bot.send_message(
        ADMIN_ID,
        "📤 উত্তোলন রিকোয়েস্ট!\n👤 ইউজার আইডি:"
        f" {target_id}\n💳 মাধ্যম: Binance Pay\n🆔 বাইনান্স পে আইডি (Pay ID):"
        f" `{wit_data['pay_id']}`\n💰 পরিমাণ: {wit_data['amount']}"
        f" টাকা\n💱 রেট: ১$ = {EXCHANGE_RATE}৳",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    await query.edit_message_text(
        "✅ বাইনান্স পে মাধ্যম সিলেক্ট হয়েছে। অ্যাডমিন প্যানেলে রিকোয়েস্ট পাঠানো"
        " হয়েছে।"
    )
    return

  action_type, status, target_id = data_parts[0], data_parts[1], int(data_parts[2])
  amount = float(data_parts[3])
  user_data = get_user_data(target_id)

  if action_type == "dep":
    if status == "approve":
      new_bal = round(user_data.get("balance", 150.0) + amount, 2)
      new_dep = round(user_data.get("total_deposit", 0.0) + amount, 2)
      update_user_field(
          target_id, {"balance": new_bal, "total_deposit": new_dep}
      )
      await query.edit_message_text("✅ বাইনান্স পে জমা এপ্রুভড।")
      await context.bot.send_message(
          target_id, f"🎉 আপনার {amount} টাকার বাইনান্স পে জমা সফল হয়েছে!"
      )
    else:
      await query.edit_message_text("❌ জমা রিজেক্টড।")
      await context.bot.send_message(
          target_id, f"❌ আপনার {amount} টাকার জমা বাতিল হয়েছে।"
      )
  elif action_type == "wit":
    if status == "approve":
      new_bal = round(
          max(0.0, user_data.get("balance", 150.0) - amount), 2
      )
      update_user_field(
          target_id,
          {
              "balance": new_bal,
              "total_withdrawal": user_data.get("total_withdrawal", 0) + 1,
          },
      )
      await query.edit_message_text("✅ উত্তোলন এপ্রুভড।")
      await context.bot.send_message(
          target_id,
          f"✅ আপনার {amount} টাকা বাইনান্স পে-তে পেমেন্ট দেওয়া হয়েছে!",
      )
    else:
      await query.edit_message_text("❌ উত্তোলন রিজেক্টড।")
      await context.bot.send_message(
          target_id, f"❌ আপনার {amount} টাকা উত্তোলন রিজেক্ট করা হয়েছে।"
      )


def main():
  app = ApplicationBuilder().token(TOKEN).build()

  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("binancedeposit", binance_deposit_command))
  app.add_handler(CommandHandler("withdraw", withdraw_command))
  app.add_handler(CallbackQueryHandler(button_click))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_request))

  print("বট সফলভাবে পোলিং মোডে চালু হচ্ছে...")
  app.run_polling()


if __name__ == "__main__":
  main()
