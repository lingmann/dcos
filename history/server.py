
import logging

from flask import Flask, Response, redirect, url_for
from flask.ext.compress import Compress
from history.statebuffer import StateBuffer
from os import environ

app = Flask(__name__)
compress = Compress()
state_buffer = None


@app.route('/history/hour')
def hour():
    result = "[" + ",".join(state_buffer.entries) + "]"
    headers = {"Access-Control-Allow-Origin": "*"}
    return Response(response=result, content_type="application/json", headers=headers)


@app.route('/ping')
def ping():
    return "pong"


@app.route('/')
def home():
    return redirect(url_for('hour'))


def start(port=int(environ.get('PORT0', '5055')), urls=environ.get('MASTER_URLS', 'http://master.mesos:5050').split(",")):
    global state_buffer
    logging.basicConfig(level="INFO")
    compress.init_app(app)
    state_buffer = StateBuffer(urls)
    state_buffer.run()
    app.run(host='0.0.0.0', port=port)
