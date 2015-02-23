import json


def load_json(filename):
    with open(filename) as f:
        return json.load(f)


def load_string(filename):
    with open(filename) as f:
        return f.read()


def if_exists(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError:
        return None
