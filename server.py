# ============================================================
#  SUPER TOOLS — License Server
#  Flask + Render এ host করুন
# ============================================================

from flask import Flask, request, jsonify
import json, os, hashlib, datetime

app = Flask(__name__)

# ---- keys.json ফাইলে সব key store হবে ----
KEYS_FILE = "keys.json"

def load_keys():
    if not os.path.exists(KEYS_FILE):
        return {}
    with open(KEYS_FILE, "r") as f:
        return json.load(f)

def save_keys(data):
    with open(KEYS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---- Key validate endpoint ----
@app.route("/validate", methods=["POST"])
def validate():
    body = request.get_json(silent=True) or {}
    key  = body.get("key", "").strip().upper()

    if not key:
        return jsonify({"valid": False, "message": "KEY MISSING"})

    keys = load_keys()
    if key not in keys:
        return jsonify({"valid": False, "message": "KEY INVALID OR EXPIRED"})

    info = keys[key]

    # Expiry চেক
    expiry_str = info.get("expiry", "")
    try:
        expiry_dt = datetime.datetime.strptime(expiry_str, "%Y-%m-%d")
        now        = datetime.datetime.utcnow()
        if now > expiry_dt:
            return jsonify({"valid": False, "message": "KEY EXPIRED"})
        seconds_left = int((expiry_dt - now).total_seconds())
        expiry_fmt   = expiry_dt.strftime("%d %b %Y")
    except Exception:
        seconds_left = 86400
        expiry_fmt   = expiry_str

    return jsonify({
        "valid":            True,
        "full_name":        info.get("name", "VIP Client"),
        "user_id":          info.get("user_id", ""),
        "expiry":           expiry_str,
        "expiry_formatted": expiry_fmt,
        "seconds_left":     seconds_left,
    })

# ---- Bot থেকে key add করার endpoint ----
@app.route("/addkey", methods=["POST"])
def addkey():
    body       = request.get_json(silent=True) or {}
    secret     = body.get("secret", "")
    SERVER_SECRET = os.environ.get("SERVER_SECRET", "SUPERTOOLS2025")

    if secret != SERVER_SECRET:
        return jsonify({"ok": False, "msg": "Unauthorized"}), 403

    key     = body.get("key", "").strip().upper()
    name    = body.get("name", "User")
    user_id = str(body.get("user_id", ""))
    days    = int(body.get("days", 30))

    expiry = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    keys = load_keys()
    keys[key] = {"name": name, "user_id": user_id, "expiry": expiry}
    save_keys(keys)

    return jsonify({"ok": True, "key": key, "expiry": expiry})

# ---- Health check ----
@app.route("/")
def index():
    return jsonify({"status": "Super Tools License Server Running ✅"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
