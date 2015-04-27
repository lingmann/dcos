
import history

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
      'dcos-history = history.__main__:start'
    ]
  },
  'install_requires': [
    "Flask>=0.10.1",
    "flask-compress"
  ]
}

from setuptools import setup
setup(**config)
