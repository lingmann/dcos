
import logging

from flask import Flask, Response, redirect, url_for
from flask.ext.compress import Compress
from history.statebuffer import StateBuffer
from os import environ

app = Flask(__name__)
compress = Compress()
state_buffer = None


@app.route('/')
def home():
    return redirect(url_for('hour'))


@app.route('/ping')
def ping():
    return "pong"


@app.route('/history/last')
def last():
    return _response_(state_buffer.latest)


@app.route('/history/minute')
def minute():
    return _buffer_response_("minute")


@app.route('/history/hour')
def hour():
    return _buffer_response_("hour")


def _buffer_response_(name):
    schedule = state_buffer.schedules.get(name)
    return _response_("[" + ",".join(schedule.buffer) + "]")


def _response_(content):
    headers = {"Access-Control-Allow-Origin": "*"}
    return Response(response=content, content_type="application/json", headers=headers)


def start(
        port=int(environ.get('PORT', '15055')),
        urls=environ.get('MASTER_URLS', 'http://leader.mesos:5050').split(","),
        frequency=int(environ.get('FETCH_FREQUENCY', "2"))):
    global state_buffer
    logging.basicConfig(format='[%(levelname)s:%(asctime)s] %(message)s', level='INFO')
    compress.init_app(app)
    state_buffer = StateBuffer(urls, frequency)
    state_buffer.run()
    app.run(host='0.0.0.0', port=port)
