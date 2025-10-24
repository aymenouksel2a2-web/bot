#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeowSSH Bot – Channel-Only + Anti-Spam + Timeout 30sec + Web-Alive:
- يعمل فقط داخل مجموعتك المحددة بالـ CHANNEL_ID
- إذا أُضيف إلى مجموعة أخرى → يُظهر رسالة توجيه للمجموعة الحقيقية
- كل مستخدم: حساب SSH واحد فقط كل 3 ساعات
- مؤقت 30 ثانية لمنع الضغط المتكرر + حذف رسائل المستخدم والبوت + timeout داخلي 30 ثانية
- كل شيء بالعربية وبدون أخطاء HTML
- Flask ويب صغير لرابط UptimeRobot
"""

import subprocess, sys, requests, time
from datetime import datetime, timedelta
from threading import Timer

# تثبيت المكتبة تلقائياً
try:
    import telebot
    from telebot import types
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pyTelegramBotAPI"])
    import telebot
    from telebot import types

BOT_TOKEN   = "8365239927:AAHi945VJbQh6vDrSwGUotVg2CN9VqNLkDA"
CHANNEL_ID  = -1002479732983   # ← ايدي مجموعتك
CHANNEL_USER= "@aynHTTPXCHAT"  # ← يوزر مجموعتك

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# Flask ويب صغير
from flask import Flask
from threading import Thread

web_app = Flask('')

@web_app.route('/')
def home():
    return "I'm alive!"

def run_web():
    web_app.run(host='0.0.0.0', port=8080, debug=False)

def keep_alive():
    Thread(target=run_web, daemon=True).start()

# قواميس عالمية
last_account_time = {}   # وقت آخر حساب لكل مستخدم
user_data = {}           # بيانات آخر حساب لكل مستخدم
last_click_time = {}     # مؤقت الضغط الأخير (منع spam)
user_timeout = {}        # timeout للمستخدمين (30 ثانية)

# === إنشاء حساب SSH جديد ===
def create_ssh():
    url = "https://painel.meowssh.shop:5000/test_ssh_public"
    hdr = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json", "Content-Type": "application/json",
        "Origin": "https://painel.meowssh.shop", "Referer": "https://painel.meowssh.shop/"
    }
    r = requests.post(url, headers=hdr, json={"store_owner_id": 1}, timeout=15)
    r.raise_for_status()
    d = r.json()
    # ترجمة المدة إلى العربية
    valid_ar = d['Expiracao'].replace("hora(s)", "ساعات").replace("horas", "ساعات").replace("hora", "ساعة")
    return {
        "user": d['Usuario'],
        "pass": d['Senha'],
        "limit": d['limite'],
        "valid": valid_ar,
        "time": datetime.now().strftime('%H:%M')
    }

def format_real(data):
    """نformats الحساب الحقيقي"""
    return (
        f"🐱 <b>تم إنشاء حساب القط!</b>  -  {data['time']}\n\n"
        f"👤 <b>اسم المستخدم:</b> <code>{data['user']}</code>\n"
        f"🔑 <b>كلمة المرور:</b> <code>{data['pass']}</code>\n"
        f"📊 <b>الحد الأقصى:</b> {data['limit']}\n"
        f"⏳ <b>مدة الصلاحية:</b> {data['valid']}"
    )

def fake_account_text(remaining_seconds, user_id):
    """نُعيد نفس بيانات الحساب الأخير لكن بمدة = الوقت المتبقي"""
    if user_id not in user_data:
        return "❌ لا يوجد حساب سابق."
    data = user_data[user_id]
    hours, rem = divmod(remaining_seconds, 3600)
    mins, _ = divmod(rem, 60)
    valid_fake = f"{hours} ساعة و {mins} دقيقة"
    return (
        f"🐱 <b>تم إنشاء حساب القط!</b>  -  {data['time']}\n\n"
        f"👤 <b>اسم المستخدم:</b> <code>{data['user']}</code>\n"
        f"🔑 <b>كلمة المرور:</b> <code>{data['pass']}</code>\n"
        f"📊 <b>الحد الأقصى:</b> {data['limit']}\n"
        f"⏳ <b>مدة الصلاحية:</b> {valid_fake}"
    )

def can_get_account(user_id):
    """نتحقق إذا كان المستخدم يستطيع الحصول على حساب جديد"""
    if user_id not in last_account_time:
        return True, 0
    elapsed = datetime.now() - last_account_time[user_id]
    remaining_seconds = 3 * 3600 - int(elapsed.total_seconds())
    if remaining_seconds <= 0:
        return True, 0
    return False, remaining_seconds

def can_click_again(user_id):
    """نمنع الضغط المتكرر خلال 30 ثانية"""
    if user_id not in last_click_time:
        return True, 0
    elapsed = time.time() - last_click_time[user_id]
    remaining = 30 - int(elapsed)
    if remaining <= 0:
        return True, 0
    return False, remaining

def is_user_in_timeout(user_id):
    """نتحقق إذا كان المستخدم في timeout (30 ثانية)"""
    if user_id not in user_timeout:
        return False, 0
    elapsed = datetime.now() - user_timeout[user_id]
    remaining_seconds = 30 - int(elapsed.total_seconds())
    if remaining_seconds <= 0:
        del user_timeout[user_id]
        return False, 0
    return True, remaining_seconds

# === لوحة أزرار دائمة (زر واحد فقط) ===
def main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    keyboard.add(types.KeyboardButton("إنشاء حساب القط🐱"))
    return keyboard

# === معالجات الأوامر والأزرار ===
@bot.message_handler(commands=['start'])
def cmd_start(message):
    # === منع الاستخدام خارج مجموعتك ===
    if message.chat.id != CHANNEL_ID:
        bot.send_message(message.chat.id,
                         f"📍 البوت يمكنك استخدامه فقط في المجموعة: {CHANNEL_USER}",
                         parse_mode="HTML")
        return

    bot.send_message(message.chat.id, "أهلاً بك! اضغط الزر أدناه لإنشاء حسابك ⬇️",
                     parse_mode="HTML", reply_markup=main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == "إنشاء حساب القط🐱")
def handle_cat_button(message):
    # === منع الاستخدام خارج مجموعتك ===
    if message.chat.id != CHANNEL_ID:
        bot.send_message(message.chat.id,
                         f"📍 البوت يمكنك استخدامه فقط في المجموعة: {CHANNEL_USER}",
                         parse_mode="HTML")
        return

    user_id = message.from_user.id

    # === التحقق من timeout 30 ثانية ===
    in_timeout, timeout_remaining = is_user_in_timeout(user_id)
    if in_timeout:
        # حذف رسالة المستخدم + رسالة تنبيه مؤقتة
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        temp = bot.send_message(message.chat.id,
                                f"⏳ يرجى الانتظار {timeout_remaining} ثانية قبل المحاولة مرة أخرى.",
                                parse_mode="HTML")
        Timer(3.0, lambda: bot.delete_message(temp.chat.id, temp.message_id)).start()
        return

    # === منع الضغط المتكرر خلال 30 ثانية ===
    can_click, remain_sec = can_click_again(user_id)
    if not can_click:
        # حذف رسالة المستخدم + وضع timeout لمدة 30 ثانية
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        user_timeout[user_id] = datetime.now()  # تسجيل وقت الـ timeout
        
        temp = bot.send_message(message.chat.id,
                                f"⏳ تم تقييدك مؤقتاً لمدة 30 ثانية بسبب الضغط المتكرر.",
                                parse_mode="HTML")
        Timer(3.0, lambda: bot.delete_message(temp.chat.id, temp.message_id)).start()
        return

    # نسجل الضغطة ونُكمل المنطق السابق
    last_click_time[user_id] = time.time()

    # === المنطق السابق (3 ساعات + نفس البيانات) ===
    can_get, remaining = can_get_account(user_id)

    if can_get:
        try:
            data = create_ssh()
            user_data[user_id] = data
            last_account_time[user_id] = datetime.now()
            bot.send_message(message.chat.id, format_real(data), parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ خطأ:\n<code>{e}</code>", parse_mode="HTML")
    else:
        fake_text = fake_account_text(remaining, user_id)
        bot.send_message(message.chat.id, fake_text, parse_mode="HTML")

# === تشغيل البوت + صفحة ويب صغيرة ===
if __name__ == "__main__":
    keep_alive()  # تشغيل Flask ويب
    print("🤖 Bot is starting with 3-hours limit + 30s anti-spam + Timeout 30sec + Groups-Only + Web-Alive ...")
    
    # ✅ حذف الـ webhook أولاً
    bot.remove_webhook()
    print("✅ Webhook removed successfully!")
    
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
