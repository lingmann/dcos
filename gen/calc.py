import json
import os
import urllib.request
from math import floor
from subprocess import check_output


def calulate_dcos_image_commit(arguments):
    dcos_image_commit = os.getenv('DCOS_IMAGE_COMMIT', None)

    if dcos_image_commit is None:
        dcos_image_commit = check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()

    if dcos_image_commit is None:
        raise "Unable to set dcos_image_commit from teamcity or git."

    return dcos_image_commit


def calculate_bootstrap(arguments):
    bootstrap_url = arguments['repository_url']
    if arguments['release_name']:
        bootstrap_url += '/' + arguments['release_name']
    return bootstrap_url


def calculate_bootstrap_id(arguments):
    url = '{}/{}/bootstrap.latest'.format(arguments['repository_url'], arguments['release_name'])
    return urllib.request.urlopen(url).read().decode('utf-8')


def calculate_fallback_dns(arguments):
    # Validation because accidentally slicing a string instead of indexing a
    # list of resolvers then finding out at cluster launch is painful.
    assert isinstance(arguments['resolvers'], str)
    resolvers = json.loads(arguments['resolvers'])
    assert isinstance(resolvers, list)
    return resolvers[0]


must = {
    'master_quorum': lambda arguments: floor(int(arguments['num_masters']) / 2) + 1,
    'fallback_dns': calculate_fallback_dns,
    'dcos_image_commit': calulate_dcos_image_commit
}

can = {
    'bootstrap_url': calculate_bootstrap,
    'bootstrap_id': calculate_bootstrap_id
}


def validate(arguments):
    assert(int(arguments['num_masters']) in [1, 3, 5, 7, 9])

    assert arguments['repository_url'][-1] != '/'

    if len(arguments['release_name']):
        assert arguments['release_name'][0] != '/'
        assert arguments['release_name'][-1] != '/'

defaults = {
  "num_masters": 3,
  "release_name": "testing/continuous",
  "repository_url": "https://downloads.mesosphere.com/dcos"
}

parameters = ["repository_url", "release_name"]
