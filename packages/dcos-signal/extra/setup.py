from setuptools import setup

config = {
    'name': 'dcos-signal',
    'version': "0.0.9",
    'description': 'Sends cluster information to segmentio',
    'author': 'Michael Jin',
    'author_email': 'michael@mesosphere.io',
    'maintainer': 'Mesosphere',
    'maintainer_email': 'support@mesosphere.io',
    'url': 'https://github.com/mesosphere/dcos-signal',
    'packages': ['dcos_signal'],
    'entry_points': {
        'console_scripts': ['dcos-signal = dcos_signal:main']
    },
    'install_requires': [
        "analytics-python",
        "docopt"
    ]
}

setup(**config)
