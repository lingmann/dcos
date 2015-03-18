#!/usr/bin/python
"""
Usage:
    cloud_config_cf <cf_template> <cloud_config>
"""

import docopt
import json
import sys


TEMPLATE_VARIABLE="$CLOUD_CONFIG"


def escape_cloud_config(content_str):
    return json.dumps(content_str)


def main():
    args = docopt.docopt(
            __doc__,
            version=0.1)

    cf_contents = ""
    with open(args['<cf_template>']) as cf_template_file:
        cf_contents = cf_template_file.read()


    cloud_config_contents = ""
    with open(args['<cloud_config>']) as cloud_config_file:
        cloud_config_contents = cloud_config_file.read()

    sys.stdout.write(cf_contents.replace(TEMPLATE_VARIABLE, escape_cloud_config(cloud_config_contents)))

    sys.stdout.flush()



if __name__ == "__main__":
    main()
