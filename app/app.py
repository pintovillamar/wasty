from flask import request
from flask_cors import CORS

from database import create_app, db

import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

app = create_app()

from models.zone     import zone_blueprint
from models.qr       import qr_blueprint
from models.report   import report_blueprint, process_message
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
