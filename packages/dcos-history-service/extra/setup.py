import history

from setuptools import setup

config = {
    'name': 'dcos-history',
    'version': history.__version__,
    'description': 'Buffers the state of the mesos leading master state',
    'author': 'Matthias',
    'author_email': 'matthias@mesosphere.io',
    'maintainer': 'Mesosphere',
    'maintainer_email': 'support@mesosphere.io',
    'url': 'https://github.com/mesosphere/dcos-history-service',
    'packages': [
        'history'
    ],
    'entry_points': {
        'console_scripts': [
            'dcos-history = history.server:start'
        ]
    },
    'install_requires': [
        "Flask>=0.10.1",
        "flask-compress",
        "requests"
    ]
}

setup(**config)
