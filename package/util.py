import json


def load_json(filename):
    with open(filename) as f:
        usage = json.load(f)
        print(usage)


def load_string(filename):
    with open(filename) as f:
        return f.read()
