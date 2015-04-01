
from flask import Flask, Response
from history.statebuffer import StateBuffer
from flask.ext.compress import Compress
import logging
from os import environ

app = Flask(__name__)
compress = Compress()
buffer = None

@app.route('/history/hour')
def hour():
    result = "[" +  ",".join(buffer.entries) + "]"
    headers = { "Access-Control-Allow-Origin": "*" }
    return Response(response=result, content_type="application/json", headers=headers)

def start(port = int(environ.get('PORT0', '5000')), urls = environ["MASTER_URLS"].split(",")):
    global buffer
    logging.basicConfig(level="INFO")
    compress.init_app(app)
    buffer = StateBuffer(urls)
    buffer.run()
    app.run(host='0.0.0.0', port=port)

