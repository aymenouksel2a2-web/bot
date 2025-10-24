#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MeowSSH Bot - Flask Webhook Version
- Anti-Spam: 30 ثانية بين كل ضغطة
- Timeout: 30 ثانية عند الضغط المتكرر
- 3 ساعات بين كل حساب SSH جديد
- زر تحميل التطبيق
- حذف تلقائي للرسائل التحذيرية
"""

from flask import Flask, request
import requests, time, threading
from datetime import datetime, timedelta

BOT_TOKEN   = "8288789847:AAHSGOPiKHtZU1b3qpfoz5h4ByeUTco0gv8"
CHANNEL_ID  = -1002479732983
CHANNEL_USER= "@aynHTTPXCHAT"

app = Flask(__name__)

# قواميس عالمية
last_account_time = {}   # آخر وقت حصل فيه المستخدم على حساب حقيقي
user_data = {}           # بيانات آخر حساب للمستخدم
last_click_time = {}     # آخر وقت ضغط فيه المستخدم (للـ anti-spam)
user_timeout = {}        # المستخدمين المحظورين مؤقتاً

# === إنشاء حساب SSH جديد ===
def create_ssh():
    """إنشاء حساب SSH من API"""
    url = "https://painel.meowssh.shop:5000/test_ssh_public"
    hdr = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://painel.meowssh.shop",
        "Referer": "https://painel.meowssh.shop/"
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

# === تنسيق رسائل الحساب ===
def format_real(data):
    """تنسيق رسالة الحساب الحقيقي"""
    return (
        f"🐱 <b>تم إنشاء حساب القط!</b>  -  {data['time']}\n\n"
        f"👤 <b>اسم المستخدم:</b> <code>{data['user']}</code>\n"
        f"🔑 <b>كلمة المرور:</b> <code>{data['pass']}</code>\n"
        f"📊 <b>الحد الأقصى:</b> {data['limit']}\n"
        f"⏳ <b>مدة الصلاحية:</b> {data['valid']}"
    )

def fake_account_text(remaining_seconds, user_id):
    """رسالة الحساب المزيف (نفس البيانات القديمة مع وقت متبقي)"""
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

# === فحص القيود الزمنية ===
def can_get_account(user_id):
    """فحص إذا مر 3 ساعات على آخر حساب حقيقي"""
    if user_id not in last_account_time:
        return True, 0
    
    elapsed = datetime.now() - last_account_time[user_id]
    remaining_seconds = 3 * 3600 - int(elapsed.total_seconds())
    
    if remaining_seconds <= 0:
        return True, 0
    
    return False, remaining_seconds

def can_click_again(user_id):
    """فحص إذا مر 30 ثانية على آخر ضغطة (anti-spam)"""
    if user_id not in last_click_time:
        return True, 0
    
    elapsed = time.time() - last_click_time[user_id]
    remaining = 30 - int(elapsed)
    
    if remaining <= 0:
        return True, 0
    
    return False, remaining

def is_user_in_timeout(user_id):
    """فحص إذا كان المستخدم في timeout (30 ثانية)"""
    if user_id not in user_timeout:
        return False, 0
    
    elapsed = datetime.now() - user_timeout[user_id]
    remaining_seconds = 30 - int(elapsed.total_seconds())
    
    if remaining_seconds <= 0:
        del user_timeout[user_id]
        return False, 0
    
    return True, remaining_seconds

# === دوال Telegram API ===
def send_message(chat_id, text, parse_mode="HTML", reply_markup=None):
    """إرسال رسالة"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    response = requests.post(url, json=payload)
    return response.json()

def delete_message(chat_id, message_id):
    """حذف رسالة"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def delete_message_after_delay(chat_id, message_id, delay=3):
    """حذف رسالة بعد فترة زمنية"""
    def delete_task():
        time.sleep(delay)
        delete_message(chat_id, message_id)
    
    threading.Thread(target=delete_task, daemon=True).start()

# === لوحات المفاتيح ===
def main_keyboard():
    """لوحة مفاتيح دائمة مع زرين"""
    return {
        "keyboard": [
            [
                {"text": "إنشاء حساب القط🐱"},
                {"text": "تحميل تطبيق القط📱"}
            ]
        ],
        "resize_keyboard": True
    }

def download_inline_keyboard():
    """زر inline لرابط التحميل"""
    return {
        "inline_keyboard": [
            [{"text": "📥 تحميل التطبيق", "url": "https://t.me/aynhttpx/26"}]
        ]
    }

# === معالجات الرسائل ===
def handle_start(chat_id):
    """معالج أمر /start"""
    send_message(
        chat_id,
        "أهلاً بك! اضغط الزر أدناه لإنشاء حسابك ⬇️",
        reply_markup=main_keyboard()
    )

def handle_download(chat_id):
    """معالج زر تحميل التطبيق"""
    send_message(
        chat_id,
        "📱 <b>تطبيق القط متاح الآن!</b>\n\n"
        "اضغط الزر أدناه لتحميل التطبيق ⬇️",
        reply_markup=download_inline_keyboard()
    )

def handle_create_account(chat_id, user_id, message_id):
    """معالج زر إنشاء حساب القط"""
    
    # === 1. فحص timeout (30 ثانية للمحظورين مؤقتاً) ===
    in_timeout, timeout_remaining = is_user_in_timeout(user_id)
    if in_timeout:
        delete_message(chat_id, message_id)
        
        result = send_message(
            chat_id,
            f"⏳ يرجى الانتظار {timeout_remaining} ثانية قبل المحاولة مرة أخرى."
        )
        
        # حذف رسالة التحذير بعد 3 ثواني
        if result.get("ok") and "result" in result:
            warning_msg_id = result["result"]["message_id"]
            delete_message_after_delay(chat_id, warning_msg_id, 3)
        
        return
    
    # === 2. فحص anti-spam (30 ثانية بين كل ضغطة) ===
    can_click, remain_sec = can_click_again(user_id)
    if not can_click:
        # حذف رسالة المستخدم
        delete_message(chat_id, message_id)
        
        # إضافة المستخدم إلى timeout
        user_timeout[user_id] = datetime.now()
        
        # إرسال رسالة تحذير
        result = send_message(
            chat_id,
            f"⏳ تم تقييدك مؤقتاً لمدة 30 ثانية بسبب الضغط المتكرر.\n"
            f"الوقت المتبقي: {remain_sec} ثانية."
        )
        
        # حذف رسالة التحذير بعد 3 ثواني
        if result.get("ok") and "result" in result:
            warning_msg_id = result["result"]["message_id"]
            delete_message_after_delay(chat_id, warning_msg_id, 3)
        
        return
    
    # === 3. تسجيل وقت الضغطة ===
    last_click_time[user_id] = time.time()
    
    # === 4. فحص إذا مر 3 ساعات على آخر حساب ===
    can_get, remaining = can_get_account(user_id)
    
    if can_get:
        # إنشاء حساب جديد حقيقي
        try:
            ssh_data = create_ssh()
            user_data[user_id] = ssh_data
            last_account_time[user_id] = datetime.now()
            send_message(chat_id, format_real(ssh_data))
        except Exception as e:
            send_message(chat_id, f"⚠️ خطأ في إنشاء الحساب:\n<code>{e}</code>")
    else:
        # إرسال نفس الحساب القديم مع وقت متبقي
        fake_text = fake_account_text(remaining, user_id)
        send_message(chat_id, fake_text)

# === مسارات Flask ===
@app.route('/')
def home():
    """الصفحة الرئيسية"""
    return "🐱 MeowSSH Bot is running! ✅"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    """معالج webhook من Telegram"""
    try:
        data = request.get_json()
        
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            user_id = message["from"]["id"]
            text = message.get("text", "")
            message_id = message["message_id"]
            
            # === فحص إذا كانت الرسالة من المجموعة الصحيحة ===
            if chat_id != CHANNEL_ID:
                send_message(
                    chat_id,
                    f"📍 البوت يمكنك استخدامه فقط في المجموعة: {CHANNEL_USER}"
                )
                return {"ok": True}
            
            # === معالجة الأوامر ===
            if text == "/start":
                handle_start(chat_id)
            
            elif text == "تحميل تطبيق القط📱":
                handle_download(chat_id)
            
            elif text == "إنشاء حساب القط🐱":
                handle_create_account(chat_id, user_id, message_id)
        
        return {"ok": True}
    
    except Exception as e:
        print(f"❌ Error in webhook: {e}")
        return {"ok": False, "error": str(e)}

# === تشغيل التطبيق ===
if __name__ == "__main__":
    print("🤖 MeowSSH Bot - Starting...")
    print(f"📍 Channel ID: {CHANNEL_ID}")
    print(f"📍 Channel Username: {CHANNEL_USER}")
    print("⚙️ Anti-Spam: 30 seconds")
    print("⚙️ Timeout: 30 seconds")
    print("⚙️ Account Cooldown: 3 hours")
    print("=" * 50)
    
    # ملاحظة: يجب تعيين الـ webhook يدوياً أو من خلال سكريبت منفصل
    # مثال: https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://YOUR_DOMAIN/{BOT_TOKEN}
    
    app.run(host='0.0.0.0', port=8080)
