#!/opt/mesosphere/bin/python3

import http.client
import json
import logging
import os
import socket
import subprocess

logging.getLogger().setLevel(
    getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper()))

reboot_count = 0
with open("/opt/mesosphere/reboot_count", "r") as fobj:
    reboot_count = int(fobj.read())

with open("/opt/mesosphere/reboot_count", "w") as fobj:
    fobj.write(str(reboot_count + 1))

def loaded(unit):
    out = subprocess.check_output(
        "systemctl status {}; exit 0".format(unit),
        shell=True).decode("utf-8")
    if "Loaded: not-found" in out:
        logging.debug(out)
        return False
    return True

def hook(data):
    client = http.client.HTTPSConnection("hooks.slack.com")
    resp = client.request(
        "POST", "/services/T0252D4NY/B08N4AW12/KN07X7zl6nWquZIfAjqOszGE",
        body=json.dumps({
            "text": data
        }))

def report_fail(problems):
    hook("not-found ({}): {}".format(socket.gethostname(),
        ", ".join(problems)))

def report_success():
    hook("all-found: reboot #{}".format(reboot_count))

problems = [u for u in os.listdir("/etc/systemd/system/dcos.target.wants")
    if not loaded(u)]

if len(problems) > 0:
    logging.debug("not-found: {}".format(", ".join(problems)))
    report_fail(problems)
else:
    logging.debug("all-found: {}".format(reboot_count))
    report_success()

    if reboot_count < 20:
        subprocess.check_output("sudo reboot", shell=True)


