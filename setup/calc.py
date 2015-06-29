import urllib.request
from math import floor


def calculate_bootstrap(arguments):
    bootstrap_url = arguments['repository_url']
    if arguments['release_name']:
        bootstrap_url += '/' + arguments['release_name']
    return bootstrap_url


def calculate_bootstrap_id(arguments):
    url = '{}/{}/bootstrap.latest'.format(arguments['repository_url'], arguments['release_name'])
    return urllib.request.urlopen(url).read().decode('utf-8')


must = {
    'master_quorum': lambda arguments: floor(int(arguments['num_masters']) / 2) + 1,
    'fallback_dns': lambda arguments: arguments['resolvers'][0]
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

