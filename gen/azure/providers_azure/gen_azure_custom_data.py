#!/usr/bin/env python3

# Requirements:
# pip install pyyaml

import re
import sys
import json

import yaml


if len(sys.argv) != 2:
    print("Usage: {} CLOUD-CONFIG.yaml".format(sys.argv[0]))
    sys.exit(1)

with open(sys.argv[1]) as f:
    config = yaml.load(f)

j = json.dumps(config, sort_keys=True)

print("[base64(concat('#cloud-config\n\n', ", end='')

prevend = 0
for m in re.finditer('(?P<pre>.*?)\[\[\[(?P<inject>.*?)\]\]\]', j):
    before = m.group('pre')
    param = m.group('inject')
    print("'{}', {},".format(before, param), end='')
    prevend = m.end()

print("'{}'))]".format(j[prevend:]), end='')
