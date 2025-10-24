#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, request
import requests, time
from datetime import datetime, timedelta

BOT_TOKEN   = "8288789847:AAHSGOPiKHtZU1b3qpfoz5h4ByeUTco0gv8"
CHANNEL_ID  = -1002479732983
CHANNEL_USER= "@aynHTTPXCHAT"

app = Flask(__name__)

# قواميس عالمية
last_account_time = {}
user_data = {}
last_click_time = {}
user_timeout = {}

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
    valid_ar = d['Expiracao'].replace("hora(s)", "ساعات").replace("horas", "ساعات").replace("hora", "ساعة")
    return {
        "user": d['Usuario'],
        "pass": d['Senha'],
        "limit": d['limite'],
        "valid": valid_ar,
        "time": datetime.now().strftime('%H:%M')
    }

def format_real(data):
    return (
        f"🐱 <b>تم إنشاء حساب القط!</b>  -  {data['time']}\n\n"
        f"👤 <b>اسم المستخدم:</b> <code>{data['user']}</code>\n"
        f"🔑 <b>كلمة المرور:</b> <code>{data['pass']}</code>\n"
        f"📊 <b>الحد الأقصى:</b> {data['limit']}\n"
        f"⏳ <b>مدة الصلاحية:</b> {data['valid']}"
    )

def fake_account_text(remaining_seconds, user_id):
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
    if user_id not in last_account_time:
        return True, 0
    elapsed = datetime.now() - last_account_time[user_id]
    remaining_seconds = 3 * 3600 - int(elapsed.total_seconds())
    if remaining_seconds <= 0:
        return True, 0
    return False, remaining_seconds

def can_click_again(user_id):
    if user_id not in last_click_time:
        return True, 0
    elapsed = time.time() - last_click_time[user_id]
    remaining = 30 - int(elapsed)
    if remaining <= 0:
        return True, 0
    return False, remaining

def is_user_in_timeout(user_id):
    if user_id not in user_timeout:
        return False, 0
    elapsed = datetime.now() - user_timeout[user_id]
    remaining_seconds = 30 - int(elapsed.total_seconds())
    if remaining_seconds <= 0:
        del user_timeout[user_id]
        return False, 0
    return True, remaining_seconds

def send_message(chat_id, text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    requests.post(url, json=payload)

def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    requests.post(url, json=payload)

@app.route('/')
def home():
    return "Bot is running! ✅ 🐱"

@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            user_id = message["from"]["id"]
            text = message.get("text", "")
            message_id = message["message_id"]
            
            if chat_id != CHANNEL_ID:
                send_message(chat_id, f"📍 البوت يمكنك استخدامه فقط في المجموعة: {CHANNEL_USER}")
                return {"ok": True}
            
            if text == "/start":
                send_message(chat_id, "أهلاً بك! اكتب: إنشاء حساب القط🐱")
                return {"ok": True}
            
            if text == "إنشاء حساب القط🐱":
                in_timeout, timeout_remaining = is_user_in_timeout(user_id)
                if in_timeout:
                    delete_message(chat_id, message_id)
                    send_message(chat_id, f"⏳ يرجى الانتظار {timeout_remaining} ثانية قبل المحاولة مرة أخرى.")
                    return {"ok": True}
                
                can_click, remain_sec = can_click_again(user_id)
                if not can_click:
                    delete_message(chat_id, message_id)
                    user_timeout[user_id] = datetime.now()
                    send_message(chat_id, f"⏳ تم تقييدك مؤقتاً لمدة 30 ثانية بسبب الضغط المتكرر.")
                    return {"ok": True}
                
                last_click_time[user_id] = time.time()
                can_get, remaining = can_get_account(user_id)
                
                if can_get:
                    try:
                        ssh_data = create_ssh()
                        user_data[user_id] = ssh_data
                        last_account_time[user_id] = datetime.now()
                        send_message(chat_id, format_real(ssh_data))
                    except Exception as e:
                        send_message(chat_id, f"⚠️ خطأ:\n<code>{e}</code>")
                else:
                    fake_text = fake_account_text(remaining, user_id)
                    send_message(chat_id, fake_text)
        
        return {"ok": True}
    except Exception as e:
        print(f"Error: {e}")
        return {"ok": False}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
