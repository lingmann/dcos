from setuptools import setup

config = {
    'name': 'dcos-history',
    'version': '0.1.0',
    'description': 'Buffers the state of the mesos leading master state',
    'author': 'Michael Ellenburg',
    'author_email': 'mellenburg@mesosphere.io',
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
        'Flask>=0.10.1',
        'flask-compress',
        'requests']
}

setup(**config)
