import sys
import os

# Add the project root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app import create_app, db as _db 
from app.models.zone import Zone, zone_schema, ZoneSchema
from app.models.qr import QR, qr_schema, QRSchema
from app.models.reporter import Reporter, reporter_schema, ReporterSchema
from app.models.report import Report, report_schema, ReportSchema

# from app.schemas.zone_schema import ZoneSchema
# from app.schemas.qr_schema import QRSchema
# from app.schemas.reporter_schema import ReporterSchema
# from app.schemas.report_schema import ReportSchema

@pytest.fixture(scope='module')
def test_app():
    app = create_app()
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()

@pytest.fixture(scope='function')
def db_session(test_app):
    connection = _db.engine.connect()
    transaction = connection.begin()
    options = dict(bind=connection, binds={})
    session = _db._make_scoped_session(options=options)
    _db.session = session
    yield session
    session.remove()
    transaction.rollback()
    connection.close()

# Zone
def test_zone_crud_and_schema(db_session):
    # Create
    zone = Zone(zone_name='Test Zone', zone_description='A test zone', zone_created='2023-10-01', zone_updated='2023-10-01')
    db_session.add(zone)
    db_session.commit()
    assert zone.zone_id is not None
    assert zone.zone_name == 'Test Zone'
    assert zone.zone_description == 'A test zone'

    # Schema serialization
    data = ZoneSchema().dump(zone)
    assert data['zone_name'] == 'Test Zone'

    # Update
    zone.zone_name = 'Updated Zone'
    db_session.commit()
    assert db_session.query(Zone).filter_by(zone_name='Updated Zone').count() == 1

    # Delete
    db_session.delete(zone)
    db_session.commit()
    assert db_session.query(Zone).filter_by(zone_name='Updated Zone').count() == 0

# Reporter
def test_reporter_crud_and_constraints(db_session):
    reporter = Reporter(reporter_numero='+51123456790', reporter_id_reporter='reporter123', reporter_created='2023-10-01', reporter_updated='2023-10-01')
    db_session.add(reporter)
    db_session.commit()
    assert reporter.reporter_id_reporter is not None

    # Invalid numero format
    with pytest.raises(Exception):
        bad = Reporter(reporter_numero='123')
        db_session.add(bad)
        db_session.commit()

    # Schema serialization
    data = ReporterSchema().dump(reporter)
    assert data['reporter_numero'] == '+51123456790'

    db_session.delete(reporter)
    db_session.commit()

# QR model tests
def test_qr_relations_and_schema(db_session):
    # Set up Zone and reporter
    zone = Zone(zone_name='Test Zone', zone_description='A test zone', zone_created='2023-10-01', zone_updated='2023-10-01')
    reporter = Reporter(reporter_numero='+51999999999', reporter_id_reporter='reporter12345', reporter_created='2023-10-01', reporter_updated='2023-10-01')
    db_session.add_all([zone, reporter])
    db_session.commit()

    qr = QR(zone_id=zone.zone_id, reporter_id=reporter.reporter_id_reporter)
    db_session.add(qr)
    db_session.commit()
    assert qr.qr_id is not None
    assert qr.zone_id == zone.zone_id
    assert qr.reporter_id == reporter.reporter_id_reporter

    # Schema serialization
    data = QRSchema().dump(qr)
    assert data['qr_id'] == qr.qr_id
    assert data['zone_id'] == zone.zone_id

    db_session.delete(qr)
    db_session.delete(zone)
    db_session.delete(reporter)
    db_session.commit()

# Report model tests
def test_report_model_full_flow(db_session):
    # Create requiered reporter
    reporter = Reporter(reporter_numero='+51999999999', reporter_id_reporter='reporter123', reporter_created='2023-10-01', reporter_updated='2023-10-01')
    db_session.add(reporter)
    db_session.commit()

    report = Report(report_status='pending', zone_id=1, reporter_id=reporter.reporter_id)
    db_session.add(report)
    db_session.commit()
    assert report.report_id is not None
    assert report.report_status == 'pending'

    # Update status
    report.report_status = '1'
    db_session.commit()
    assert db_session.query(Report).filter_by(report_status='1').one()

    # Related reporter access
    fetched = db_session.query(Report).first()
    assert fetched.reporter.reporter_id == reporter.reporter_id

    # Schema serialization
    data = ReportSchema().dump(report)
    assert data['report_status'] == '1'

    # Cleanup
    db_session.delete(report)
    db_session.delete(reporter)
    db_session.commit()

def test_full_report_flow_integration(test_app, db_session, monkeypatch):
    client = test_app.test_client()

    sent = []
    # Mockeamos send_waha_text para capturar su payload
    def fake_send(token, mensaje):
        sent.append(mensaje)
        return {"status": "ok"}

    monkeypatch.setattr("app.app.send_waha_text", fake_send)

    # Paso 1: Usuario inicia reporte (payload tipo WAHA)
    inicio_payload = {
        "session": "abc123",
        "message": {"type": "text", "text": "Quiero reportar este punto"}
    }
    resp = client.post("/webhook", json=inicio_payload)
    assert resp.status_code == 200

    # Debe haberse enviado un mensaje con instrucciones de confirmación
    assert any("¿Confirmas" in m for m in sent)

    # Paso 2: Usuario confirma con “1”
    sent.clear()
    confirm_payload = {
        "session": "abc123",
        "message": {"type": "text", "text": "1"}
    }
    resp = client.post("/webhook", json=confirm_payload)
    assert resp.status_code == 200

    # Ahora debe haberse creado un Report en la BD
    report = db_session.query(Report).filter_by(session_key="abc123").one()
    assert report.report_status == "OPEN"

    # Y debe enviarse el mensaje de “gracias”
    assert any("Gracias por tu reporte" in m for m in sent)
