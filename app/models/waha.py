from flask import Flask, request
import requests
import json


app = Flask(__name__)

# WAHA endpoint
WAHA_SEND_URL = "http://192.168.1.16:3000/api/sendText"  # Change if WAHA is on a different host
SESSION_NAME = "default"

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    data = request.get_json()

    # Listen to "message.any" events
    if data.get("event") == "message.any":
        return process_message(data.get("payload", {}))
    
    return "OK"

def save_message_to_txt(info, filename="messages_log.txt"):
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(info, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")

def extract_message_info(payload):
    msg_data = payload.get("_data", {})

    from_raw = msg_data.get("from")
    if isinstance(from_raw, dict):
        sender_number = from_raw.get("user")
        sender_wa_id = from_raw.get("_serialized")
    else:
        sender_number = from_raw.split("@")[0] if from_raw else None
        sender_wa_id = from_raw

    message_id = msg_data.get("id", {}).get("_serialized")

    info = {
        "sender_number": sender_number,
        "sender_wa_id": sender_wa_id,
        "message_id": message_id,
        "text": msg_data.get("body"),
        "timestamp": msg_data.get("t") or payload.get("timestamp"),
        "message_type": msg_data.get("type"),
        "ack": msg_data.get("ack"),
        "is_new": msg_data.get("isNewMsg"),
        "is_forwarded": msg_data.get("isForwarded"),
        "has_media": msg_data.get("hasMedia"),
        "links": msg_data.get("links", []),
    }

    save_message_to_txt(info)  # Save to .txt
    print("Extracted and saved message info:", info)
    return info

def process_message(payload):
    body = payload.get("body", "")
    sender = payload.get("from")

    if body.lower().startswith(".") and sender:
        send_waha_text(sender, "pong")
        print(payload)
    
    return "OK"


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
        print(f"Sent to {chat_id}: {response.status_code} - {response.text}")
        return response.ok
    except Exception as e:
        print(f"Error sending WAHA message: {e}")
        return False
    
def send_simple_button(chat_id):
    payload = {
        "chatId": chat_id,
        "replyTo": None,
        "selectedDisplayText": "string",
        "selectedButtonID": "string",
        "session": "default",
        "buttons": [
            {
            "type": "reply",
            "text": "I am good!"
            },
            {
            "type": "call",
            "text": "Call us",
            "phoneNumber": "+1234567890"
            },
            {
            "type": "copy",
            "text": "Copy code",
            "copyCode": "4321"
            },
            {
            "type": "url",
            "text": "How did you do that?",
            "url": "https://waha.devlike.pro"
            }
        ],
    }

    response = requests.post("http://localhost:3000/api/sendButtons", json=payload)
    print(response.status_code, response.text)


def send_color_question(chat_id):
    payload = {
        "chatId": chat_id,
        "header": "How are you?",
        "body": "Tell us how are you please 🙏",
        "footer": "If you have any questions, please send it in the chat",
        "buttons": [
            {
            "type": "reply",
            "text": "I am good!"
            },
            {
            "type": "call",
            "text": "Call us",
            "phoneNumber": "+1234567890"
            },
            {
            "type": "copy",
            "text": "Copy code",
            "copyCode": "4321"
            },
            {
            "type": "url",
            "text": "How did you do that?",
            "url": "https://waha.devlike.pro"
            }
        ],
        "session": "default"
    }

    try:
        response = requests.post("http://localhost:3000/api/sendButtons", json=payload)
        print(f"Sent button message to {chat_id}. Status: {response.status_code} | {response.text}")
        return response.ok
    except Exception as e:
        print(f"Error sending sendButtons message: {e}")
        return False


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
