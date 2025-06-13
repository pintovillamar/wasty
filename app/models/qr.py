import sys
import os

# Add the project root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Blueprint, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug import exceptions

import requests
import json
from datetime import datetime 

from database import db, ma

class QR(db.Model):
    __tablename__ = 'qr'
    qr_id = db.Column(db.Integer, primary_key=True)
    qr_string = db.Column(db.String(100), nullable=False)
    qr_lat = db.Column(db.Float, nullable=False)
    qr_lon = db.Column(db.Float, nullable=False)
    qr_created = db.Column(db.DateTime, default=datetime.utcnow)
    qr_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign keys
    zone_id = db.Column(db.Integer, db.ForeignKey('zone.zone_id'), nullable=False)

    def __init__(self, qr_string, qr_lat, qr_lon, qr_created, qr_updated, zone_id):
        self.qr_string = qr_string
        self.qr_lat = qr_lat
        self.qr_lon = qr_lon
        self.qr_created = qr_created
        self.qr_updated = qr_updated
        self.zone_id = zone_id

    def __repr__(self):
        return f"QR('{self.qr_string}', '{self.qr_lat}', '{self.qr_lon}', '{self.qr_created}', '{self.qr_updated}', '{self.zone_id}')"

class QRSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = QR
        load_intance = True
        include_fk = True
        fields = (
            'qr_id',
            'qr_string',
            'qr_lat',
            'qr_lon',
            'qr_created',
            'qr_updated',
            'zone_id'
        )
    
qr_schema = QRSchema()
qrs_schema = QRSchema(many=True)

class QRModel:
    def create_qr(self):
        new_qr = QR(
            request.json['qr_string'],
            request.json['qr_lat'],
            request.json['qr_lon'],
            datetime.now(), # created
            datetime.now(), # updated
            request.json['zone_id']  # zone_id 
        )

        db.session.add(new_qr)
        db.session.commit()
        
        return qr_schema.jsonify(new_qr)
    

# Blueprints (temp)

model = QRModel()
qr_blueprint = Blueprint('qr_blueprint', __name__)

@qr_blueprint.route('/create_qr', methods=['POST'])
@cross_origin()
def create_qr():
    return model.create_qr()

@qr_blueprint.route('/qrs', methods=['GET'])
@cross_origin()
def get_qrs():
    all_qrs = QR.query.all()
    return qrs_schema.jsonify(all_qrs)

@qr_blueprint.route('/qr/<int:qr_id>', methods=['GET'])
@cross_origin()
def get_qr(qr_id):
    qr = QR.query.get_or_404(qr_id)
    return qr_schema.jsonify(qr)

@qr_blueprint.route('/qr/<int:qr_id>', methods=['PUT'])
@cross_origin()
def update_qr(qr_id):
    qr = QR.query.get_or_404(qr_id)
    if 'qr_string' in request.json:
        qr.qr_string = request.json['qr_string']
    if 'qr_lat' in request.json:
        qr.qr_lat = request.json['qr_lat']
    if 'qr_lon' in request.json:
        qr.qr_lon = request.json['qr_lon']
    qr.qr_updated = datetime.now()
    if 'zone_id' in request.json:
        qr.zone_id = request.json['zone_id']

    db.session.commit()
    return qr_schema.jsonify(qr)

@qr_blueprint.route('/qr/<int:qr_id>', methods=['DELETE'])
@cross_origin()
def delete_qr(qr_id):
    qr = QR.query.get_or_404(qr_id)
    db.session.delete(qr)
    db.session.commit()
    return jsonify({'message': 'QR deleted successfully'}), 204

@qr_blueprint.route('/qrs/count', methods=['GET'])
@cross_origin()
def count_qrs():
    count = QR.query.count()
    return jsonify({'qr count': count})