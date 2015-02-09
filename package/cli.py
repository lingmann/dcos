
"""DCOS Package management local utility

Usage:
  dcos-pkg list
  dcos-pkg active
  dcos-pkg fetch <id>
  dcos-pkg activate <id>...
"""

from docopt import docopt
from package.constants import version

if __name__ == "__main__":
    arguments = docopt(__doc__, version="DCOS Package {}".format(version))
    print(arguments)
