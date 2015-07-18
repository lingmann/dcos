import boto3
import os

if 'ENV_AWS_CONFIG' in os.environ:
    session_prod = boto3.session.Session(
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name='us-east-1'
        )
    session_dev = None
else:
    session_prod = boto3.session.Session(profile_name='production')
    session_dev = boto3.session.Session(profile_name='development')
