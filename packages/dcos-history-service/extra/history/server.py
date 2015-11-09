
import logging

from flask import Flask, Response
from flask.ext.compress import Compress
from history.statebuffer import StateBuffer
from os import environ

app = Flask(__name__)
compress = Compress()
state_buffer = None


@app.route('/')
def home():
    return _response_("history/last - to get the last fetched state\n" +
                      "history/minute - to get the state array of the last minute\n" +
                      "history/hour - to get the state array of the last hour\n" +
                      "ping - to get a pong\n")


@app.route('/ping')
def ping():
    return "pong"


@app.route('/history/last')
def last():
    return _response_(state_buffer.last)


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
    headers = {
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "accept, accept-charset, accept-encoding, " +
                                        "accept-language, authorization, content-length, " +
                                        "content-type, host, origin, proxy-connection, " +
                                        "referer, user-agent, x-requested-with",
        "Access-Control-Allow-Methods": "HEAD, GET, PUT, POST, PATCH, DELETE",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Max-Age": "86400"
    }
    return Response(response=content, content_type="application/json", headers=headers)


def start(
        port=int(environ.get('PORT', '15055')),
        frequency=int(environ.get('FETCH_FREQUENCY', "2"))):
    global state_buffer
    logging.basicConfig(format='[%(levelname)s:%(asctime)s] %(message)s', level='INFO')

    compress.init_app(app)
    state_buffer = StateBuffer(frequency)
    state_buffer.run()
    app.run(host='0.0.0.0', port=port)
