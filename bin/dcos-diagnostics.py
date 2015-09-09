#!/opt/mesosphere/bin/python
"""DCOS Diagnostics Tool

Checks the health of the current node.
Exits with 0 if everything is healthy.
Exits with 1 if problems are detected.
"""

import sys
import subprocess
import os
import re

def dcos_units():
    units = ["dcos-setup.service",
            "link-env.service",
            "dcos-download.service"]
    for u in os.listdir("/etc/systemd/system/dcos.target.wants"):
        units.append(os.path.basename(u))
    return(units)

# Return a Dict of systemd unit parameters
def unit_params(unit):
    params = {}
    pattern = re.compile('(?P<key>\w+)=(?P<value>.*)')
    unit_param_str = subprocess.check_output(
            ["systemctl", "show", "--all", unit]).decode("utf-8")
    for line in unit_param_str.split(os.linesep):
        m = pattern.match(line)
        if m:
            params[m.group('key')] = m.group('value')
    return(params)

# Return True or False
def is_unit_healthy(unit):
    checks = { "Result":"success", "LoadState":"loaded" }
    params = unit_params(unit)
    is_healthy = True
    for k,v in checks.items():
        if k not in params or params[k] != v:
            is_healthy = False
    return(is_healthy)

def main():
    exit_status = 0
    for unit in dcos_units():
        if not is_unit_healthy(unit):
            print("{}: ERROR".format(unit))
            exit_status = 1
    sys.exit(exit_status)

if __name__ == "__main__":
    main()
