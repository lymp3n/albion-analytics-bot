import os
from flask import Flask
from threading import Thread
from waitress import serve
import logging

app = Flask('')
logger = logging.getLogger('keep_alive')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting keep_alive server on port {port}")
    serve(app, host='0.0.0.0', port=port, _quiet=True)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
