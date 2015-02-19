
"""DCOS Package management local utility

Usage:
  pkgpanda --bootstrap
  pkgpanda list
  pkgpanda active
  pkgpanda fetch <id>
  pkgpanda activate <id>...
"""

from docopt import docopt
from package.constants import version

if __name__ == "__main__":
    arguments = docopt(__doc__, version="DCOS Package {}".format(version))
    print(arguments)
