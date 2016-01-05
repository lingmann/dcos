"""
Glue code for logic around calling associated backend
libraries to support the dcos installer.
"""
from providers.genconf import do_genconf


def configure(cli_args):
    do_genconf(cli_args)
