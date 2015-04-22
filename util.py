import boto3
import requests

bucket = boto3.resource('s3').Bucket('downloads.mesosphere.io')


def render_markdown_data(data):
    return requests.post(
            "https://api.github.com/markdown/raw",
            headers={'Content-type': 'text/plain'},
            data=data
            ).text


def render_markdown(path_to_md):
    return render_markdown_data(open(path_to_md, 'r'))


def upload_s3(name, path, dest_path=None, args={}, no_cache=False):
    if no_cache:
        args['CacheControl'] = 'no-cache'

    with open(path, 'rb') as data:
        print("Uploading {}{}".format(path, " as {}".format(dest_path) if dest_path else ''))
        if not dest_path:
            dest_path = path
        return bucket.Object('dcos/{name}/{path}'.format(name=name, path=dest_path)).put(Body=data, **args)
