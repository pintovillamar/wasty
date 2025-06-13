# models/reporter.py
import sys
import os

# Add the project root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from database import db, ma

# NO importes Report aquí en el top‐level. 
# Basta con usar el nombre "Report" (como string) en la relación.
class Reporter(db.Model):
    __tablename__ = 'reporter'

    reporter_id          = db.Column(db.Integer, primary_key=True)
    reporter_numero      = db.Column(db.String(100), nullable=False, unique=True)
    reporter_id_reporter = db.Column(db.String(100), nullable=False)
    reporter_reports     = db.Column(db.Integer, default=0)
    reporter_created     = db.Column(db.DateTime, default=datetime.utcnow)
    reporter_updated     = db.Column(db.DateTime, default=datetime.utcnow)

    # “Report” se resolverá más tarde (SQLAlchemy lo buscará cuando ya exista la clase Report)
    reports = db.relationship('Report', backref='reporter', lazy=True)

    def __init__(self, reporter_numero, reporter_id_reporter, reporter_created, reporter_updated):
        self.reporter_numero      = reporter_numero
        self.reporter_id_reporter = reporter_id_reporter
        self.reporter_created     = reporter_created
        self.reporter_updated     = reporter_updated

    def __repr__(self):
        return (
            f"Reporter('{self.reporter_numero}', "
            f"'{self.reporter_id_reporter}', "
            f"{self.reporter_reports}, "
            f"'{self.reporter_created}', "
            f"'{self.reporter_updated}')"
        )


class ReporterSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model         = Reporter
        load_instance = True       # ¡Ojo al typo: debe ser "load_instance", no "load_intance"!
        include_fk    = True
        fields        = (
            'reporter_id',
            'reporter_numero',
            'reporter_id_reporter',
            'reporter_reports',
            'reporter_created',
            'reporter_updated',
        )

reporter_schema  = ReporterSchema()
reporters_schema = ReporterSchema(many=True)


class ReporterModel:
    def create_reporter(self):
        from flask import request  # importar request aquí (si es que lo usas)
        new_reporter = Reporter(
            reporter_numero      = request.json['reporter_numero'],
            reporter_id_reporter = request.json['reporter_id_reporter'],
            reporter_created     = datetime.utcnow(),
            reporter_updated     = datetime.utcnow()
        )
        db.session.add(new_reporter)
        db.session.commit()
        return reporter_schema.jsonify(new_reporter)


# Blueprints para Reporter
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

    # Importa el modelo aquí, no en el top‐level (rompe el ciclo)
# (Podría quedar así):
# from models.reporter import Reporter, reporter_schema, reporters_schema

reporter_blueprint = Blueprint('reporter_blueprint', __name__)

@reporter_blueprint.route('/create_reporter', methods=['POST'])
@cross_origin()
def create_reporter():
    return ReporterModel().create_reporter()

@reporter_blueprint.route('/reporters', methods=['GET'])
@cross_origin()
def get_reporters():
    all_reporters = Reporter.query.all()
    return reporters_schema.jsonify(all_reporters)

@reporter_blueprint.route('/reporter/<int:reporter_id>', methods=['GET'])
@cross_origin()
def get_reporter(reporter_id):
    reporter = Reporter.query.get_or_404(reporter_id)
    return reporter_schema.jsonify(reporter)

@reporter_blueprint.route('/reporter/<int:reporter_id>', methods=['PUT'])
@cross_origin()
def update_reporter(reporter_id):
    reporter = Reporter.query.get_or_404(reporter_id)
    data = request.json
    if 'reporter_numero' in data:
        reporter.reporter_numero = data['reporter_numero']
    if 'reporter_id_reporter' in data:
        reporter.reporter_id_reporter = data['reporter_id_reporter']
    reporter.reporter_updated = datetime.utcnow()
    db.session.commit()
    return reporter_schema.jsonify(reporter)

@reporter_blueprint.route('/reporter/<int:reporter_id>', methods=['DELETE'])
@cross_origin()
def delete_reporter(reporter_id):
    reporter = Reporter.query.get_or_404(reporter_id)
    db.session.delete(reporter)
    db.session.commit()
    return jsonify({'message': 'Reporter deleted successfully'}), 204

@reporter_blueprint.route('/reporters/count', methods=['GET'])
@cross_origin()
def count_reporters():
    count = Reporter.query.count()
    return jsonify({'reporters count': count})