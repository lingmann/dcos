from flask import Flask
from fabric.api import run
import logging as log

def run():
    log.info("Executing Flask server...")
    app = Flask(__name__)
    @app.route('/')
    def fuck():
        return "This is fucked."

    app.run()

