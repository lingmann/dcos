from flask import Flask
from flask import render_template
from fabric.api import run
import logging as log



def run(options):
    """
    Define some routes and execute the Flask server. Currently
    pinning the routes with v1.0 to allow for seamless upgrades
    in the future.
    """
    log.info("Executing Flask server...")
    app = Flask(__name__)
    do_routes(app,options)
    app.run()

def do_routes(app,options):
    @app.route('/installer/v1.0/')
    def mainpage():
        return render_template('main.html', title='Flask Test')


