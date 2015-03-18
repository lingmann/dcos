#!/usr/bin/python
"""
Usage:
    cloud_config_cf <cf_template> <cloud_config>
"""

import docopt
import json
import re
import sys


TEMPLATE_VARIABLE="$CLOUD_CONFIG"
AWS_REF_REGEX = re.compile(r"(?P<before>.*)(?P<ref>{.*})(?P<after>.*)")


def escape_cloud_config(content_str):
    return json.dumps(content_str)

def transform(line):
    m = AWS_REF_REGEX.search(line)
    # no splitting necessary
    if not m:
        return "%s,\n" % (json.dumps(line))

    before = m.group('before')
    ref = m.group('ref')
    after = m.group('after')

    transformed_before = "%s" % (json.dumps(before))
    transformed_ref = ref
    transformed_after =  "%s" % (json.dumps(after))
    return "%s, %s, %s, %s,\n" % (transformed_before, transformed_ref, transformed_after, '"\\n"')


def main():
    args = docopt.docopt(
            __doc__,
            version=0.1)

    cf_contents = ""
    with open(args['<cf_template>']) as cf_template_file:
        cf_contents = cf_template_file.read()


    cloud_config_contents = ""

    transformed_string = ""
    with open(args['<cloud_config>']) as cloud_config_file:
        for line in cloud_config_file:
            transformed_string += transform(line)
    cloud_config_contents = "".join(transformed_string).rstrip(',\n')

    sys.stdout.write(cf_contents.replace(TEMPLATE_VARIABLE, cloud_config_contents))

    sys.stdout.flush()



if __name__ == "__main__":
    main()
