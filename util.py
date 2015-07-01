from botocore.client import ClientError
import boto3
import requests

aws_prod_session = boto3.session.Session(profile_name='production')


def render_markdown_data(data):
    return requests.post(
            "https://api.github.com/markdown/raw",
            headers={'Content-type': 'text/plain'},
            data=data
            ).text


def render_markdown(path_to_md):
    return render_markdown_data(open(path_to_md, 'r'))


def get_object(release_name, path):
    bucket = aws_prod_session.resource('s3').Bucket('downloads.mesosphere.io')

    return bucket.Object('dcos/{name}/{path}'.format(name=release_name, path=path))


def upload_s3(release_name, path, dest_path=None, args={}, no_cache=False,  if_not_exists=False):
    if no_cache:
        args['CacheControl'] = 'no-cache'

    if not dest_path:
        dest_path = path

    s3_object = get_object(release_name, dest_path)

    if if_not_exists:
        try:
            s3_object.load()
            print("Skipping {}: already exists".format(dest_path))
            return s3_object
        except ClientError:
            pass

    with open(path, 'rb') as data:
        print("Uploading {}{}".format(path, " as {}".format(dest_path) if dest_path else ''))
        return s3_object.put(Body=data, **args)
