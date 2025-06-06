from flask import request
from flask_cors import CORS
import requests

from database import create_app, db
from datetime import datetime, timedelta

active_sessions   = {}
SESSION_DURATION  = timedelta(minutes=5)

WAHA_SEND_URL = "http://192.168.1.16:3000/api/sendText"
SESSION_NAME  = "default"

app = create_app()

from models.zone     import zone_blueprint
from models.qr       import qr_blueprint
from models.report   import report_blueprint
from models.reporter import reporter_blueprint

app.register_blueprint(zone_blueprint)
app.register_blueprint(qr_blueprint)
app.register_blueprint(report_blueprint)
app.register_blueprint(reporter_blueprint)

CORS(app, supports_credentials=True)


@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    data = request.get_json()

    if data.get("event") == "message.any" and isinstance(data.get("payload"), dict):
        return process_message(data["payload"])

    return "[WEBHOOK ENDPOINT] OK", 200


def process_message(payload):

    # 0) Si viene fromMe == True (mensaje del bot), lo ignoramos
    if payload.get("fromMe", False):
        return "[IGNORANDO MENSAJE PROPIO] OK", 200

    # 1) Extraer 'body' y 'from'
    body = (payload.get("body") or "").strip()
    sender = payload.get("from") 
    if not body or not sender:
        return "[PROCESS MESSAGE] OK", 200

    reporter_numero = sender.split("@")[0]       # "51990025356"
    reporter_id_rep = reporter_numero + "@c.us"  # "51990025356@c.us"
    now = datetime.utcnow()

    from models.reporter import Reporter
    from models.report   import Report, report_schema

    # Opening
    if body.lower() == "quiero reportar este punto. [test1]":
        active_sessions[reporter_numero] = now + SESSION_DURATION

        send_waha_text(
            sender,
            "Por favor responde con 0 (vacío) o 1 (lleno) para finalizar el reporte."
        )
        print(f"[SESSION START] reporter={reporter_numero}, expires_at={active_sessions[reporter_numero]}")
        return "[PROCESS MESSAGE] OK", 200

    # 3) Cierre de sesión: "0" o "1"
    if body in ("0", "1"):
        exp = active_sessions.get(reporter_numero)
        # 3a) Si no hay sesión activa o expiró
        if exp is None or now > exp:
            active_sessions.pop(reporter_numero, None)
            send_waha_text(sender, "No tienes una sesión activa, tienes que escanear el código otra vez para reportar.")
            print(f"[SESSION EXPIRED/NOT FOUND] reporter={reporter_numero}")
            return "[PROCESS MESSAGE] OK", 200

        # 3b) Sesión válida: buscar/crear Reporter en BD
        reporter = Reporter.query.filter_by(reporter_numero=reporter_numero).first()
        if not reporter:
            reporter = Reporter(
                reporter_numero      = reporter_numero,
                reporter_id_reporter = reporter_id_rep,
                reporter_created     = now,
                reporter_updated     = now
            )
            db.session.add(reporter)
            db.session.commit()

        # Crear el Report con status="0" o "1"
        new_report = Report(
            report_status  = body,
            report_created = now,
            report_updated = now,
            zone_id        = 1,
            reporter_id    = reporter.reporter_id
        )
        db.session.add(new_report)

        # Actualizar contador en Reporter
        reporter.reporter_reports = (reporter.reporter_reports or 0) + 1
        reporter.reporter_updated = now

        db.session.commit()
        active_sessions.pop(reporter_numero, None)

        send_waha_text(sender, "El reporte finalizó, gracias por tu reporte.")
        print(f"[SESSION CLOSED] reporter={reporter_numero}, outcome={body}, report_id={new_report.report_id}")
        return "[PROCESS MESSAGE] OK", 200

    # 4) Si llega otro texto DURANTE la sesión (no expiró)
    exp = active_sessions.get(reporter_numero)
    if exp is not None and now <= exp:
        send_waha_text(sender, "Durante la sesión solo puedes enviar 0 o 1 para cerrarla.")
        print(f"[INVALID DURING SESSION] reporter={reporter_numero}, text={body}")
        return "[PROCESS MESSAGE] OK", 200

    # 5) No hay sesión activa y el texto no coincide con la pregunta inicial
    return "[PROCESS MESSAGE] OK", 200



def send_waha_text(chat_id, text):
    payload = {
        "chatId":                 chat_id,
        "reply_to":               None,
        "text":                   text,
        "linkPreview":            True,
        "linkPreviewHighQuality": False,
        "session":                SESSION_NAME
    }
    try:
        resp = requests.post(WAHA_SEND_URL, json=payload)
        print(f"[SEND WAHA TEXT] Sent to {chat_id}: {resp.status_code} - {resp.text}")
        return resp.ok
    except Exception as e:
        print(f"[SEND WAHA TEXT] Error sending WAHA message: {e}")
        return False


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
