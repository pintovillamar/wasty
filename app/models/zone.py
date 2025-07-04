# Modelos SQLAlchemy

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

class Zone(db.Model):
    __tablename__ = 'zone'
    __table_args__ = {'extend_existing': True}
    zone_id = db.Column(db.Integer, primary_key=True)
    zone_name = db.Column(db.String(100), nullable=False)
    zone_description = db.Column(db.String(255), nullable=True)
    zone_created = db.Column(db.DateTime, default=datetime.utcnow)
    zone_updated = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, zone_name, zone_description, zone_created, zone_updated):
        self.zone_name = zone_name
        self.zone_description = zone_description
        self.zone_created = zone_created
        self.zone_updated = zone_updated

    def __repr__(self):
        return f"Zone('{self.zone_name}', '{self.zone_description}', '{self.zone_created}', '{self.zone_updated}')"


class ZoneSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Zone
        load_intance = True
        fields = ('zone_id', 'zone_name', 'zone_description', 'zone_created', 'zone_updated')
    
zone_schema = ZoneSchema()
zones_schema = ZoneSchema(many=True)

class ZoneModel:
    def create_zone(self):
        new_zone = Zone(
            request.json['zone_name'],
            request.json['zone_description'],
            datetime.now(), # created
            datetime.now()  # updated 
        )

        db.session.add(new_zone)
        db.session.commit()
        
        return zone_schema.jsonify(new_zone)
    

# Blueprints (temp)

model = ZoneModel()
zone_blueprint = Blueprint('zone_blueprint', __name__)

@zone_blueprint.route('/create_zone', methods=['POST'])
@cross_origin()
def create_zone():
    return model.create_zone()

@zone_blueprint.route('/zones', methods=['GET'])
@cross_origin()
def get_zones():
    all_zones = Zone.query.all()
    return zones_schema.jsonify(all_zones)

@zone_blueprint.route('/zone/<int:zone_id>', methods=['GET'])
@cross_origin()
def get_zone(zone_id):
    zone = Zone.query.get_or_404(zone_id)
    return zone_schema.jsonify(zone)

@zone_blueprint.route('/zone/<int:zone_id>', methods=['PUT'])
@cross_origin()
def update_zone(zone_id):
    zone = Zone.query.get_or_404(zone_id)
    
    if 'zone_name' in request.json:
        zone.zone_name = request.json['zone_name']
    if 'zone_description' in request.json:
        zone.zone_description = request.json['zone_description']
    zone.zone_updated = datetime.now()

    db.session.commit()
    return zone_schema.jsonify(zone)

@zone_blueprint.route('/zone/<int:zone_id>', methods=['DELETE'])
@cross_origin()
def delete_zone(zone_id):
    zone = Zone.query.get_or_404(zone_id)
    db.session.delete(zone)
    db.session.commit()
    return jsonify({'message': 'Zone deleted successfully'}), 204

@zone_blueprint.route('/zones/count', methods=['GET'])
@cross_origin()
def count_zones():
    count = Zone.query.count()
    return jsonify({'zone count': count})