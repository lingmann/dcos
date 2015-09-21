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


def validate_cloud_config(cc_string):
    """Check for any invalid characters in the cloud config, and exit with an
    error message if any invalid characters are detected."""
    illegal_pattern = re.compile("[']")
    illegal_match = illegal_pattern.search(cc_string)
    if illegal_match:
        print("ERROR: Illegal cloud config string detected.", file=sys.stderr)
        print("ERROR: {} matches pattern {}".format(
            illegal_match.string, illegal_match.re), file=sys.stderr)
        sys.exit(1)

with open(sys.argv[1]) as f:
    config = yaml.load(f)

j = json.dumps(config, sort_keys=True)

print("[base64(concat('#cloud-config\n\n', ", end='')

prevend = 0
for m in re.finditer('(?P<pre>.*?)\[\[\[(?P<inject>.*?)\]\]\]', j):
    before = m.group('pre')
    validate_cloud_config(before)
    param = m.group('inject')
    print("'{}', {},".format(before, param), end='')
    prevend = m.end()

validate_cloud_config(j[prevend:])
print("'{}'))]".format(j[prevend:]), end='')
