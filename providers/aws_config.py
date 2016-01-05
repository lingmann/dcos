import os

import boto3

if 'ENV_AWS_CONFIG' in os.environ:
    session_prod = boto3.session.Session(
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', 'Set AWS_ACCESS_KEY_ID to use session_prod'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', 'Set AWS_SECRET_ACCESS_KEY to use session_prod'),
        region_name='us-east-1'
        )
    session_dev = boto3.session.Session(
        aws_access_key_id=os.getenv('AWS_DEV_ACCESS_KEY_ID', 'Set AWS_DEV_ACCESS_KEY_ID to use session_dev'),
        aws_secret_access_key=os.getenv(
            'AWS_DEV_SECRET_ACCESS_KEY', 'Set AWS_DEV_SECRET_ACCESS_KEY to use session_dev'),
        region_name='us-east-1'
        )
else:
    session_prod = boto3.session.Session(profile_name='production')
    session_dev = boto3.session.Session(profile_name='development')
