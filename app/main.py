from flask import Flask, request
import requests
import json


app = Flask(__name__)

# WAHA endpoint
WAHA_SEND_URL = "http://192.168.1.15:3000/api/sendText"  # Change if WAHA is on a different host
SESSION_NAME = "default"

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    data = request.get_json()

    # Listen to "message.any" events
    if data.get("event") == "message.any":
        return process_message(data.get("payload", {}))
    
    return "[WEBHOOK ENDPOINT] OK"

def process_message(payload):
    body = payload.get("body", "")
    sender = payload.get("from")

    if body == "ping" and sender:
        send_waha_text(sender, "pong")
        print("[INCOMING MESSAGE] -> ", body)
    
    return "[PROCESS MESSAGE] OK"

def send_waha_text(chat_id, text):
    payload = {
        "chatId": chat_id,
        "reply_to": None,
        "text": text,
        "linkPreview": True,
        "linkPreviewHighQuality": False,
        "session": SESSION_NAME
    }

    try:
        response = requests.post(WAHA_SEND_URL, json=payload)
        print(f"[SEND WAHA TEXT] Sent to {chat_id}: {response.status_code} - {response.text}")
        return response.ok
    except Exception as e:
        print(f"[SEND WAHA TEXT] Error sending WAHA message: {e}")
        return False

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
