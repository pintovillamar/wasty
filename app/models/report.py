# models/report.py
import sys
import os

# Add the project root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from datetime import datetime

from database import db, ma

class Report(db.Model):
    __tablename__ = 'report'

    report_id     = db.Column(db.Integer, primary_key=True)
    report_status = db.Column(db.String(50), nullable=False)
    report_created= db.Column(db.DateTime, default=datetime.utcnow)
    report_updated= db.Column(db.DateTime, default=datetime.utcnow)

    zone_id     = db.Column(db.Integer, db.ForeignKey('zone.zone_id'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('reporter.reporter_id'), nullable=False)

    def __init__(self, report_status, report_created, report_updated, zone_id, reporter_id):
        self.report_status  = report_status
        self.report_created = report_created
        self.report_updated = report_updated
        self.zone_id        = zone_id
        self.reporter_id    = reporter_id

    def __repr__(self):
        return (
            f"Report('{self.report_status}', "
            f"'{self.report_created}', "
            f"'{self.report_updated}', "
            f"{self.zone_id}, "
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
            'zone_id',
            'reporter_id'
        )

report_schema  = ReportSchema()
reports_schema = ReportSchema(many=True)


# NO importes Reporter en el top‐level para evitar bucle
# (si luego necesitas usar Reporter, importalo adentro de cada función)

class ReportModel:
    def create_report(self):
        new_report = Report(
            request.json['report_status'],
            datetime.utcnow(),
            datetime.utcnow(),
            request.json['zone_id'],
            request.json['reporter_id']
        )

        db.session.add(new_report)
        db.session.commit()
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
        if 'report_status' not in data or 'zone_id' not in data:
            return jsonify({
                'error': 'Para crear un Report se requiere "report_status" y "zone_id".'
            }), 400

        new_report = Report(
            report_status = data['report_status'],
            report_created= datetime.utcnow(),
            report_updated= datetime.utcnow(),
            zone_id       = data['zone_id'],
            reporter_id   = reporter.reporter_id
        )
        db.session.add(new_report)

        # 5. Incrementar contador en Reporter
        reporter.reporter_reports = (reporter.reporter_reports or 0) + 1
        reporter.reporter_updated = datetime.utcnow()

        # 6. Commit único para todo
        db.session.commit()

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
