import requests


def render_markdown(path_to_md):
    return requests.post(
            "https://api.github.com/markdown/raw",
            headers={'Content-type': 'text/plain'},
            data=open(path_to_md)
            ).text
