import dcos_signal
from setuptools import setup

config = {
    'name': 'dcos-signal',
    'version': dcos_signal.__version__,
    'description': 'Sends cluster information to segmentio',
    'author': 'Michael Jin',
    'author_email': 'michael@mesosphere.io',
    'maintainer': 'Mesosphere',
    'maintainer_email': 'support@mesosphere.io',
    'url': 'https://github.com/mesosphere/dcos-signal',
    'packages': ['dcos_signal'],
    'entry_points': {
        'console_scripts': ['dcos-signal = dcos_signal.__main__:start']
    },
    'install_requires': [
        "analytics-python",
        "docopt"
    ]
}

setup(**config)
