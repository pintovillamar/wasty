# models/report.py
import sys
import os

# Add the project root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Blueprint, request, jsonify, Response, current_app
from flask_cors import cross_origin
from datetime import datetime

import time
import threading

from database import db, ma

class Report(db.Model):
    __tablename__ = 'report'
    __table_args__ = {'extend_existing': True}
    report_id     = db.Column(db.Integer, primary_key=True)
    report_status = db.Column(db.String(50), nullable=False)
    report_created= db.Column(db.DateTime, default=datetime.utcnow)
    report_updated= db.Column(db.DateTime, default=datetime.utcnow)

    qr_id = db.Column(db.Integer, db.ForeignKey('qr.qr_id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('reporter.reporter_id'), nullable=False)

    def __init__(self, report_status, report_created, report_updated, qr_id, reporter_id):
        self.report_status  = report_status
        self.report_created = report_created
        self.report_updated = report_updated
        self.qr_id          = qr_id
        self.reporter_id    = reporter_id

    def __repr__(self):
        return (
            f"Report('{self.report_status}', "
            f"'{self.report_created}', "
            f"'{self.report_updated}', "
            f"{self.qr_id}, "
            f"{self.reporter_id})"
        )


class ReportSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Report
        load_instance = True    # fijarse en el typo: “load_instance”
        include_fk    = True
        fields        = (
            'report_id',
            'report_status',
            'report_created',
            'report_updated',
            'qr_id',
            'reporter_id'
        )

report_schema  = ReportSchema()
reports_schema = ReportSchema(many=True)

import requests
from datetime import datetime, timedelta

HOST = os.environ.get("HOST")
PORT = os.environ.get("PORT")

active_sessions   = {}
SESSION_DURATION  = timedelta(minutes=5)

WAHA_SEND_URL = f"http://{HOST}:{PORT}/api/sendText" # host and port from .env
SESSION_NAME  = "default"

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

def process_message(payload):

    # 0) Si viene fromMe == True (mensaje del bot), lo ignoramos
    if payload.get("fromMe", False):
        return "[IGNORANDO MENSAJE PROPIO] OK", 200

    # 1) Extraer 'body' y 'from'
    body = (payload.get("body") or "").strip()
    sender = payload.get("from") 
    if not body or not sender:
        return "[PROCESS MESSAGE] OK", 200

    reporter_numero = sender.split("@")[0]
    reporter_id_rep = reporter_numero + "@c.us"  
    now = datetime.utcnow()

    from models.reporter import Reporter

    # Opening
    if body.lower() == "quiero reportar este punto. [test1]":
        active_sessions[reporter_numero] = now + SESSION_DURATION

        send_waha_text(
            sender,
            "Por favor responde con: \n" \
            "0 (punto *vacío*) \n" \
            "1 (punto *lleno*)\n" \
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
            qr_id        = 1, # Asignar un QR fijo por ahora
            reporter_id    = reporter.reporter_id
        )
        db.session.add(new_report)

        # Actualizar contador en Reporter
        reporter.reporter_reports = (reporter.reporter_reports or 0) + 1
        reporter.reporter_updated = now

        db.session.commit()
        
        notify_new_report(new_report)

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

class ReportModel:
    def create_report(self):
        new_report = Report(
            request.json['report_status'],
            datetime.utcnow(),
            datetime.utcnow(),
            request.json['qr_id'],
            request.json['reporter_id']
        )

        db.session.add(new_report)
        db.session.commit()
        notify_new_report(new_report)
        print(f"[NEW REPORT] report_id={new_report.report_id}, status={new_report.report_status}")
        return report_schema.jsonify(new_report)

    def create_report_flow(self):
        from flask import request, jsonify
        # Si necesitas referirte al modelo Reporter, importalo aquí:
        from models.reporter import Reporter

        data = request.json

        # 1. Verificar que nos hayan enviado 'reporter_numero'
        if 'reporter_numero' not in data:
            return jsonify({
                'error': 'Debe enviar "reporter_numero" para identificar o crear al Reporter.'
            }), 400

        reporter_numero = data['reporter_numero']

        # 2. Intentar obtener el Reporter con ese reporter_numero
        reporter = Reporter.query.filter_by(reporter_numero=reporter_numero).first()

        # 3. Si no existe, crearlo (necesitamos reporter_id_reporter)
        if not reporter:
            if 'reporter_id_reporter' not in data:
                return jsonify({
                    'error': 'No existe ningún Reporter con ese "reporter_numero", '
                             'y además falta "reporter_id_reporter" para crearlo.'
                }), 400

            reporter = Reporter(
                reporter_numero      = reporter_numero,
                reporter_id_reporter = data['reporter_id_reporter'],
                reporter_created     = datetime.utcnow(),
                reporter_updated     = datetime.utcnow()
            )
            db.session.add(reporter)
            db.session.commit()
            # Ahora reporter.reporter_id existe

        # 4. Validar que vengan 'report_status' y 'zone_id'
        if 'report_status' not in data or 'qr_id' not in data:
            return jsonify({
                'error': 'Para crear un Report se requiere "report_status" y "qr_id".'
            }), 400

        new_report = Report(
            report_status = data['report_status'],
            report_created= datetime.utcnow(),
            report_updated= datetime.utcnow(),
            qr_id         = data['qr_id'],
            reporter_id   = reporter.reporter_id
        )
        db.session.add(new_report)

        # 5. Incrementar contador en Reporter
        reporter.reporter_reports = (reporter.reporter_reports or 0) + 1
        reporter.reporter_updated = datetime.utcnow()

        # 6. Commit único para todo
        db.session.commit()
        notify_new_report(new_report)
        print(f"[NEW REPORT] reporter={reporter_numero}, report_id={new_report.report_id}, status={new_report.report_status}")
        
        # 7. Devolver el JSON del Report recién creado
        return report_schema.jsonify(new_report), 201


# Blueprints para Report
report_blueprint = Blueprint('report_blueprint', __name__)

@report_blueprint.route('/create_report', methods=['POST'])
@cross_origin()
def create_report():
    return ReportModel().create_report()

@report_blueprint.route('/reports', methods=['GET'])
@cross_origin()
def get_reports():
    all_reports = Report.query.all()
    return reports_schema.jsonify(all_reports)

@report_blueprint.route('/report/<int:report_id>', methods=['GET'])
@cross_origin()
def get_report(report_id):
    report = Report.query.get_or_404(report_id)
    return report_schema.jsonify(report)

@report_blueprint.route('/report/<int:report_id>', methods=['PUT'])
@cross_origin()
def update_report(report_id):
    report = Report.query.get_or_404(report_id)
    data = request.json
    if 'report_status' in data:
        report.report_status = data['report_status']
    if 'zone_id' in data:
        report.zone_id = data['zone_id']
    if 'reporter_id' in data:
        report.reporter_id = data['reporter_id']
    report.report_updated = datetime.utcnow()
    db.session.commit()
    return report_schema.jsonify(report)

@report_blueprint.route('/reports/<int:reporter_id>/reports', methods=['GET'])
@cross_origin()
def get_reporter_reports(reporter_id):
    # Si accedemos a reporter.reports, SQLAlchemy ya conoce la relación
    # porque en models/reporter.py definimos `reports = relationship('Report', …)`
    from models.reporter import Reporter
    reporter = Reporter.query.get_or_404(reporter_id)
    return reports_schema.jsonify(reporter.reports)

@report_blueprint.route('/report/<int:report_id>', methods=['DELETE'])
@cross_origin()
def delete_report(report_id):
    report = Report.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    return jsonify({'message': 'Report deleted successfully'}), 204

@report_blueprint.route('/reports/count', methods=['GET'])
@cross_origin()
def count_reports():
    count = Report.query.count()
    return jsonify({'reports count': count})

@report_blueprint.route('/reports/<int:report_id>/reporter', methods=['GET'])
@cross_origin()
def get_report_reporter(report_id):
    report = Report.query.get_or_404(report_id)
    # `report.reporter` existe gracias a backref='reporter' en el modelo Reporter
    from models.reporter import reporter_schema
    return reporter_schema.jsonify(report.reporter)

@report_blueprint.route('/create_report_flow', methods=['POST'])
@cross_origin()
def create_report_flow():
    return ReportModel().create_report_flow()

new_reports_queue = []

def notify_new_report(report):
    report_json = report_schema.dumps(report)
    new_reports_queue.append(report_json)

@report_blueprint.route('/stream_reports')
@cross_origin()
def stream_reports():
    def event_stream():
        while True:
            if new_reports_queue:
                report_json = new_reports_queue.pop(0)
                print(f"[STREAM REPORT] Sending report")
                yield f"data: {report_json}\n\n"
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")