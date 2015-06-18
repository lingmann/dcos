#!/usr/bin/env python3

import json
import requests


def load_json(filename):
    try:
        with open(filename) as f:
            return json.load(f)
    except ValueError as ex:
        raise ValueError("Invalid JSON in {0}: {1}".format(filename, ex)) from ex


def write_json(filename, data):
    with open(filename, "w+") as f:
        return json.dump(data, f)


all_amis = requests.get('http://stable.release.core-os.net/amd64-usr/current/coreos_production_ami_all.json').json()

region_to_ami = {}

for ami in all_amis['amis']:
    region_to_ami[ami['name']] = {
        'stable': ami['hvm']
    }

print(json.dumps(region_to_ami, indent=2, sort_keys=True, separators=(', ', ': ')))
#The CF templates aren't real json
#cf = load_json("templates/cloudformation.json")
#cf['Mappings']['RegionToAmi'] = region_to_ami
#write_json("updated.cloudformation.json", cf)

#cf_simple = load_json("templates/simple/cloudformation.json")
#cf['Mappings']['RegionToAmi'] = region_to_ami
#write_json("updated.simple.cloudformation.json", cf)
