#!/usr/bin/env python3

import re
import sys
import json

import yaml


if len(sys.argv) != 2:
    print("Usage: {} CLOUD-CONFIG.yaml".format(sys.argv[0]))
    sys.exit(1)

with open(sys.argv[1]) as f:
    config = yaml.load(f)

j = json.dumps(config)

print("[concat('#cloud-config\\n\\n', ", end='')

prevend = 0
for m in re.finditer('(?P<parameter>parameters\(\'[a-zA-Z0-9-]+\'\))', j):
    before = j[prevend:m.start()].replace('\\', '\\\\').replace('"', '\\"')
    param = j[m.start():m.end()]

    print("'{}', {},".format(before, param), end='')

    prevend = m.end()

print("'{}')]".format(j[prevend:].replace('\\', '\\\\').replace('"', '\\"')), end='')
