# ==========================================================
#  ZENEX TELEGRAM BOT v6.5 + License Key Generator
#  Global OTP Watcher | License Management
# ==========================================================

import telebot
import requests
import time
import threading
import re
import random
import string
import datetime
from telebot import types
from concurrent.futures import ThreadPoolExecutor

# ================== CONFIG ==================
BOT_TOKEN      = "8734000495:AAFxzT9dNhP3kXHZOd83xnqf9TB55F_UvA0"
API_KEY        = "ZNX_6MFNKOEB3HFLTF2LQLD1560A"
BASE           = "https://api.zenexnetwork.com"
OTP_GROUP_ID   = -1004467990951

# ---- Render এ deploy করার পর আপনার URL দিন ----
LICENSE_SERVER = "https://key-genareted.onrender.com"
SERVER_SECRET  = "SUPERTOOLS2025"   # server.py এর সাথে মিলিয়ে রাখুন

# Admin Telegram ID (শুধু admin key বানাতে পারবে)
ADMIN_IDS = [123456789]  # আপনার Telegram ID দিন

OTP_POLL    = 1
MAX_WORKERS = 20

# ================== GLOBAL TRACKER ==================
number_owner = {}
global_seen  = set()
lock         = threading.Lock()

bot     = telebot.TeleBot(BOT_TOKEN)
headers = {"mapikey": API_KEY, "Content-Type": "application/json"}
user_data = {}

def get_user(chat_id):
    if chat_id not in user_data:
        user_data[chat_id] = {"service": None, "prefix": None, "numbers": []}
    return user_data[chat_id]

# ================== LICENSE KEY GENERATOR ==================
def generate_key(days=30):
    """Format: 20261231-XXXX-XXXX-XXXX"""
    expiry_date = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).strftime("%Y%m%d")
    parts = [''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(3)]
    return f"{expiry_date}-{parts[0]}-{parts[1]}-{parts[2]}"

def add_key_to_server(key, name, user_id, days):
    """Render server এ key পাঠাও"""
    try:
        r = requests.post(
            f"{LICENSE_SERVER}/addkey",
            json={"secret": SERVER_SECRET, "key": key, "name": name, "user_id": user_id, "days": days},
            timeout=10
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "msg": str(e)}

# ================== LICENSE COMMANDS ==================
@bot.message_handler(commands=['genkey'])
def cmd_genkey(msg):
    """Admin: key বানাও — /genkey 30 @username"""
    if msg.chat.id not in ADMIN_IDS:
        bot.reply_to(msg, "❌ *Admin only command!*", parse_mode="Markdown")
        return

    parts = msg.text.split()
    days  = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 30
    name  = parts[2] if len(parts) > 2 else "VIP Client"

    key = generate_key(days)
    result = add_key_to_server(key, name, str(msg.chat.id), days)

    if result.get("ok"):
        expiry = result.get("expiry", "N/A")
        bot.reply_to(
            msg,
            f"✅ *KEY GENERATED!*\n\n"
            f"🔑 `{key}`\n"
            f"👤 *Name:* `{name}`\n"
            f"📅 *Expires:* `{expiry}` ({days} days)\n\n"
            f"_এই key টি copy করে app এ দিন_",
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(msg, f"❌ Server Error: `{result.get('msg')}`", parse_mode="Markdown")


@bot.message_handler(commands=['mykey'])
def cmd_mykey(msg):
    """/mykey — নিজের জন্য key নিন (admin দেয়)"""
    bot.reply_to(
        msg,
        "🔑 *License Key পেতে Admin কে contact করুন।*\n\n"
        "📲 App এ key দিয়ে activate করুন।",
        parse_mode="Markdown"
    )

# ================== API ==================
def api_active_ranges(service=None):
    try:
        r = requests.get(f"{BASE}/v1/active-ranges", headers=headers, timeout=10)
        res = r.json()
        if not res.get("success"):
            return []
        ranges = res["data"]["active_ranges"]
        if service:
            ranges = [x for x in ranges if x["service"].lower() == service.lower()]
        ranges.sort(key=lambda x: x["hits"], reverse=True)
        return ranges
    except Exception as e:
        print(f"[API] Ranges Error: {e}")
        return []

def api_get_number(range_prefix):
    try:
        payload = {"range": range_prefix, "is_national": False, "remove_plus": False}
        r = requests.post(f"{BASE}/v1/getnum", headers=headers, json=payload, timeout=15)
        d = r.json()
        if d["meta"]["code"] == 200:
            return d["data"]
        return None
    except Exception as e:
        print(f"[API] GetNum Error: {e}")
        return None

def api_fetch_otps(number):
    try:
        r = requests.get(
            f"{BASE}/v1/numsuccess/info",
            headers=headers,
            params={"number": number},
            timeout=10
        )
        res = r.json()
        if res.get("meta", {}).get("code") == 200:
            return res["data"].get("otps", [])
        return []
    except Exception as e:
        print(f"[API] OTP Error: {e}")
        return []

# ================== GLOBAL OTP WATCHER ==================
def check_one_number(number):
    try:
        otps = api_fetch_otps(number)
        for item in otps:
            nid = item.get("nid") or item.get("id") or str(item)
            with lock:
                if nid in global_seen:
                    continue
                global_seen.add(nid)

            otp_raw  = item.get("otp") or item.get("code") or "N/A"
            created  = item.get("created_at", "N/A")
            codes    = re.findall(r'\b\d{4,8}\b', otp_raw)
            otp_code = codes[-1] if codes else otp_raw

            with lock:
                info = number_owner.get(number)
            if not info:
                continue

            chat_id = info["chat_id"]
            service = info["service"]

            try:
                kb  = types.InlineKeyboardMarkup()
                btn = types.InlineKeyboardButton(
                    f"📋 COPY OTP: {otp_code}",
                    copy_text=types.CopyTextButton(text=otp_code)
                )
                kb.add(btn)
                bot.send_message(
                    chat_id,
                    f"📱 `{number}`\n🌐 `{service.upper()}`\n🔑 `{otp_code}`",
                    parse_mode="Markdown", reply_markup=kb
                )
            except Exception as e:
                print(f"[WATCHER] User Send Error: {e}")

            if OTP_GROUP_ID:
                try:
                    bot.send_message(
                        OTP_GROUP_ID,
                        f"🔥 *NEW OTP*\n📱 `{number}`\n🌐 `{service.upper()}`\n🔑 `{otp_code}`\n⏰ `{created}`",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print(f"[WATCHER] Group Error: {e}")
    except Exception as e:
        print(f"[WATCHER] {number} Error: {e}")

def global_otp_watcher():
    print("[WATCHER] Started ✅")
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    while True:
        try:
            with lock:
                numbers = list(number_owner.keys())
            if numbers:
                list(executor.map(check_one_number, numbers))
        except Exception as e:
            print(f"[WATCHER] Loop Error: {e}")
        time.sleep(OTP_POLL)

# ================== KEYBOARDS ==================
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("📲 GET NUMBER"), types.KeyboardButton("🔍 SEARCH PREFIX"))
    kb.row(types.KeyboardButton("📊 ACTIVE RANGE"))
    return kb

def services_keyboard(cb_prefix="svc"):
    ranges   = api_active_ranges()
    services = sorted(set(x["service"].lower() for x in ranges))
    kb       = types.InlineKeyboardMarkup(row_width=2)
    btns     = [types.InlineKeyboardButton(f"⚡ {s.upper()}", callback_data=f"{cb_prefix}:{s}") for s in services[:20]]
    kb.add(*btns)
    kb.row(types.InlineKeyboardButton("🔙 BACK", callback_data="back_main"))
    return kb

def numbers_keyboard(service, numbers, prefix):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for n in numbers:
        kb.add(types.InlineKeyboardButton(f"📱 {n}", copy_text=types.CopyTextButton(text=n)))
    kb.row(
        types.InlineKeyboardButton("🔄 CHANGE", callback_data=f"change:{service}"),
        types.InlineKeyboardButton("➕ PREFIX",  callback_data=f"addpfx_list:{service}")
    )
    kb.row(
        types.InlineKeyboardButton("🗑️ REMOVE", callback_data="remove_prefix"),
        types.InlineKeyboardButton("🔙 MENU",   callback_data="back_main")
    )
    return kb

def prefix_list_keyboard(service, ranges):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for r in ranges[:15]:
        kb.add(types.InlineKeyboardButton(
            f"✨ {r['range']} | {r['tag']} | 🔥 {r['hits']} Hits",
            callback_data=f"setpfx:{service}:{r['range']}"
        ))
    kb.row(types.InlineKeyboardButton("🔙 BACK", callback_data=f"back_number:{service}"))
    return kb

def assign_numbers(chat_id, service, numbers):
    with lock:
        for n in numbers:
            number_owner[n] = {"chat_id": chat_id, "service": service}

# ================== HANDLERS ==================
@bot.message_handler(commands=['start'])
def cmd_start(msg):
    get_user(msg.chat.id)
    bot.send_message(
        msg.chat.id,
        "✨ *WELCOME TO ZENEX BOT v6.5* ✨\n\n⚡ *Global OTP Watcher ACTIVE.*\nSelect a service to get numbers!",
        parse_mode="Markdown", reply_markup=main_menu()
    )

@bot.message_handler(commands=['chatid'])
def cmd_chatid(msg):
    bot.reply_to(msg, f"🆔 *Chat ID:* `{msg.chat.id}`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📲 GET NUMBER")
def menu_get_number(msg):
    bot.send_message(msg.chat.id, "🎯 *Select a Service:*", parse_mode="Markdown", reply_markup=services_keyboard("svc"))

@bot.callback_query_handler(func=lambda c: c.data.startswith("svc:"))
def cb_service(call):
    svc = call.data.split(":", 1)[1]
    u   = get_user(call.message.chat.id)
    u["service"] = svc
    u["numbers"] = []
    ranges = api_active_ranges(svc)
    if not ranges:
        bot.answer_callback_query(call.id, "❌ No active ranges!")
        return
    use_prefix = u.get("prefix") or ranges[0]["range"]
    bot.answer_callback_query(call.id, "⏳ Fetching Numbers...")
    bot.edit_message_text(f"⏳ *Fetching for {svc.upper()}...*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
    numbers = []
    for _ in range(3):
        d = api_get_number(use_prefix)
        if d:
            numbers.append(d["full_number"])
        time.sleep(0.4)
    if not numbers:
        bot.edit_message_text("❌ *Failed. Try again.*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
        return
    u["numbers"] = numbers
    u["prefix"]  = use_prefix
    assign_numbers(call.message.chat.id, svc, numbers)
    bot.edit_message_text(
        f"🌐 *SERVICE:* `{svc.upper()}`\n📡 *PREFIX:* `{use_prefix}`\n\n👇 *Tap to copy:*\n⚡ *OTP Watcher:* `ACTIVE 🟢`",
        chat_id=call.message.chat.id, message_id=call.message.message_id,
        parse_mode="Markdown", reply_markup=numbers_keyboard(svc, numbers, use_prefix)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("change:"))
def cb_change(call):
    svc    = call.data.split(":", 1)[1]
    u      = get_user(call.message.chat.id)
    prefix = u.get("prefix") or (api_active_ranges(svc) or [{}])[0].get("range")
    if not prefix:
        bot.answer_callback_query(call.id, "❌ No prefix!")
        return
    bot.answer_callback_query(call.id, "🔄 Getting new numbers...")
    numbers = []
    for _ in range(3):
        d = api_get_number(prefix)
        if d:
            numbers.append(d["full_number"])
        time.sleep(0.4)
    if not numbers:
        bot.answer_callback_query(call.id, "❌ Not found!")
        return
    u["numbers"] = numbers
    assign_numbers(call.message.chat.id, svc, numbers)
    bot.edit_message_text(
        f"🔄 *NEW NUMBERS FOR {svc.upper()}*\n📡 *PREFIX:* `{prefix}`\n\n⚡ *OTP Watcher:* `ACTIVE 🟢`",
        chat_id=call.message.chat.id, message_id=call.message.message_id,
        parse_mode="Markdown", reply_markup=numbers_keyboard(svc, numbers, prefix)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("addpfx_list:"))
def cb_addpfx_list(call):
    svc    = call.data.split(":", 1)[1]
    ranges = api_active_ranges(svc)
    if not ranges:
        bot.answer_callback_query(call.id, "❌ No ranges!")
        return
    bot.answer_callback_query(call.id, "📋 Select Prefix")
    bot.edit_message_text(f"➕ *Select Prefix for {svc.upper()}:*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=prefix_list_keyboard(svc, ranges))

@bot.callback_query_handler(func=lambda c: c.data.startswith("setpfx:"))
def cb_setpfx(call):
    _, svc, rng = call.data.split(":", 2)
    u = get_user(call.message.chat.id)
    u["prefix"]  = rng
    u["service"] = svc
    bot.answer_callback_query(call.id, f"✅ Prefix: {rng}")
    numbers = []
    for _ in range(3):
        d = api_get_number(rng)
        if d:
            numbers.append(d["full_number"])
        time.sleep(0.4)
    if not numbers:
        bot.edit_message_text("❌ *No numbers for this prefix.*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
        return
    u["numbers"] = numbers
    assign_numbers(call.message.chat.id, svc, numbers)
    bot.edit_message_text(
        f"✅ *Prefix:* `{rng}`\n🌐 *Service:* `{svc.upper()}`\n\n⚡ *OTP Watcher:* `ACTIVE 🟢`",
        chat_id=call.message.chat.id, message_id=call.message.message_id,
        parse_mode="Markdown", reply_markup=numbers_keyboard(svc, numbers, rng)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("back_number:"))
def cb_back_number(call):
    svc     = call.data.split(":", 1)[1]
    u       = get_user(call.message.chat.id)
    numbers = u.get("numbers", [])
    prefix  = u.get("prefix", "")
    if not numbers:
        ranges = api_active_ranges(svc)
        if ranges:
            for _ in range(3):
                d = api_get_number(ranges[0]["range"])
                if d:
                    numbers.append(d["full_number"])
                time.sleep(0.4)
            u["numbers"] = numbers
            u["prefix"]  = ranges[0]["range"]
            prefix        = ranges[0]["range"]
            assign_numbers(call.message.chat.id, svc, numbers)
    if not numbers:
        bot.answer_callback_query(call.id, "❌ Data not found!")
        return
    bot.edit_message_text(
        f"📱 *{svc.upper()} NUMBERS*\n📡 *PREFIX:* `{prefix}`",
        chat_id=call.message.chat.id, message_id=call.message.message_id,
        parse_mode="Markdown", reply_markup=numbers_keyboard(svc, numbers, prefix)
    )

@bot.callback_query_handler(func=lambda c: c.data == "remove_prefix")
def cb_remove_prefix(call):
    u = get_user(call.message.chat.id)
    u["prefix"]  = None
    u["numbers"] = []
    bot.answer_callback_query(call.id, "🗑️ Removed!")
    bot.edit_message_text("✅ *Prefix removed.*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def cb_back(call):
    bot.edit_message_text("🏠 *Main Menu*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
    bot.send_message(call.message.chat.id, "Choose an option:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🔍 SEARCH PREFIX")
def menu_search(msg):
    bot.send_message(msg.chat.id, "🔍 *Select a Service:*", parse_mode="Markdown", reply_markup=services_keyboard("search"))

@bot.callback_query_handler(func=lambda c: c.data.startswith("search:"))
def cb_search(call):
    svc    = call.data.split(":", 1)[1]
    ranges = api_active_ranges(svc)
    if not ranges:
        bot.answer_callback_query(call.id, "❌ No prefixes found!")
        return
    lines = [f"🔍 *{svc.upper()} PREFIXES:*\n"]
    kb    = types.InlineKeyboardMarkup(row_width=1)
    for r in ranges[:10]:
        lines.append(f"📡 `{r['range']}` | {r['tag']} | 🔥 *{r['hits']}* Hits")
        kb.add(types.InlineKeyboardButton(f"➕ ADD {r['range']}", callback_data=f"setpfx:{svc}:{r['range']}"))
    kb.row(types.InlineKeyboardButton("🔙 MAIN MENU", callback_data="back_main"))
    bot.edit_message_text("\n".join(lines), chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📊 ACTIVE RANGE")
def menu_active(msg):
    ranges = api_active_ranges()
    if not ranges:
        bot.send_message(msg.chat.id, "❌ No data!")
        return
    lines = ["📊 *TOP ACTIVE RANGES*\n"]
    for r in ranges[:15]:
        lines.append(f"📡 `{r['range']}` | `{r['service'].upper()}` | {r['tag']} | 🔥 *{r['hits']}* Hits")
    bot.send_message(msg.chat.id, "\n".join(lines), parse_mode="Markdown")

# ================== RUN ==================
if __name__ == "__main__":
    print("🚀 ZENEX Bot v6.5 + License Server Started...")
    watcher = threading.Thread(target=global_otp_watcher, daemon=True)
    watcher.start()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
