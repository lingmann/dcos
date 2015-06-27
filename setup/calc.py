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
