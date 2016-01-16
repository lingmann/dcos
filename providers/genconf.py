#!/usr/bin/env python3
"""Generates DCOS packages and configuration."""

import argparse
import json
import logging as log
import os
import subprocess
import sys
from copy import deepcopy
from subprocess import CalledProcessError

import pkgpanda
import yaml

import gen
import providers.bash as bash
from deploy.clean import uninstall_dcos
from deploy.deploy import install_dcos
from deploy.postflight import run_postflight
from deploy.preflight import run_preflight


def stringify_dict(data):
    """
    For a given set of structured data, return a list as a json array in
    but in string format so it can be ingested by gen.
    """
    for key, values in data.items():
        if isinstance(values, list):
            log.debug("Caught list, transforming to JSON string: %s", list)
            data[key] = json.dumps(values)
        else:
            pass

    log.debug("Stringified genconf data: %s", data)
    return data


# NOTE: yaml_load_content can be a filename or a yaml document because yaml.load
# takes both.
def load_yaml_dict(yaml_str):
    # Load config
    config = yaml.load(yaml_str)

    # Error if top level isn't a yaml dictionary
    if not isinstance(config, dict):
        log.error("YAML configuration must be a dictionary at the top level.")
        sys.exit(1)
    return config


def get_config(options):
    """
    Checks the YAML config for baseline errors and
    returns a dictionary to caller.
    """
    genconf_config = {}
    # Load in /genconf/config.json arguments
    try:
        config = load_yaml_dict(open("/genconf/config.yaml").read())
        complete_config = deepcopy(config)

        if 'cluster_config' not in config:
            log.error('Cluster configuration file must contain a section "cluster_config" '
                      'that contains all the configuration for DCOS in the cluster.')
            sys.exit(1)
        if not isinstance(config['cluster_config'], dict):
            log.error('"cluster_config" section of configuration must contain a YAML dictionary.')
            sys.exit(1)

        if 'ssh_config' not in config:
            log.error('SSH configuration must be present in config.yaml as "ssh_config"')
            sys.exit(1)
        if not isinstance(config['ssh_config'], dict):
            log.error('"ssh_config" section of configuration must contain a YAML dictionary.')
            sys.exit(1)

        if 'log_directory' not in config['ssh_config']:
            log.error('log_directory must be present in ssh_config dictionary.')
            sys.exit(1)
        else:
            log_dir = config['ssh_config']['log_directory']
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

        genconf_config = stringify_dict((config)['cluster_config'])
        # Check a value always / only in computed configs to give a cleaner
        # message to users when they try just feeding a computed config back
        # into the generation library.
        if 'dcos_image_commit' in genconf_config:
            log.error(
                "The expanded configuration produced by the gen library cannot be fed directly"
                "back into this library as a config file. It is the full computed "
                "configuration used to flesh out the various templates, and contains "
                "multiple derived / calculated values that are asserted to be calculated "
                "(dcos_image_commit, master_quorum, etc.). All computed parameters need to be removed "
                "before the saved config can be used.")
            sys.exit(1)
    except FileNotFoundError:
        log.error("Specified config file '" + '/genconf/config.yaml' + "' does not exist")
        sys.exit(1)
    except ValueError as ex:
        log.error("%s", ex)
        sys.exit(1)
    return genconf_config, complete_config


def do_genconf(options):
    """
    Wraps calls to the gen library and instanciates configuration for a given provider.
    """
    # Interpolate the commands in genconf.py to gen library | i.e., set the args
    # in gen/__init__.py from our genconf.py commands
    genconf_config = {}
    gen_options = gen.get_options_object()
    if not options.interactive:
        genconf_config, config = get_config(options)
    gen_options.output_dir = '/genconf/serve'

    if options.interactive:
        gen_options.assume_defaults = False
        gen_options.non_interactive = False
    else:
        gen_options.assume_defaults = True
        gen_options.non_interactive = True

    subprocess.check_output(['mkdir', '-p', '/genconf/serve'])

    gen_out = do_provider(gen_options, bash, ['bash', 'centos', 'onprem'], genconf_config)

    # Pass the arguments from gen_out to download, specifically calling the bootstrap_id value
    fetch_bootstrap(gen_out.arguments['bootstrap_id'])

    # Write cluster_packages.json with a list of packages
    pkgpanda.write_json('/genconf/cluster_packages.json', gen_out.cluster_packages)


def do_provider(options, provider_module, mixins, genconf_config):
    # We set the bootstrap_id in env as to not expose it to users but still make it switchable
    if 'BOOTSTRAP_ID' in os.environ:
        bootstrap_id = os.environ['BOOTSTRAP_ID']
    else:
        log.error("BOOTSTRAP_ID must be set in environment to run.")
        sys.exit(1)

    arguments = {
        'ip_detect_filename': '/genconf/ip-detect',
        'bootstrap_id': bootstrap_id,
        'provider': 'onprem'}

    # Make sure there are no overlaps between arguments and genconf_config.
    # TODO(cmaloney): Switch to a better dictionary diff here which will
    # show all the errors at once.
    for k in genconf_config.keys():
        if k in arguments.keys():
            log.error("User config contains option `{}` already ".format(k) +
                      "provided by caller of gen.generate()")
            sys.exit(1)

    # update arguments with the genconf_config
    arguments.update(genconf_config)

    gen_out = gen.generate(
        arguments=arguments,
        options=options,
        mixins=mixins
        )
    provider_module.generate(gen_out, '/genconf/serve')
    return gen_out


def fetch_bootstrap(bootstrap_id):
    bootstrap_filename = "{}.bootstrap.tar.xz".format(bootstrap_id)
    save_path = "/genconf/serve/bootstrap/{}".format(bootstrap_filename)

    def cleanup_and_exit():
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except OSError as ex:
                log.error(ex.strerror)
        sys.exit(1)

    if os.path.exists(save_path):
        return

    # Check if there is an in-container copy of the bootstrap tarball, and
    # if so copy it across
    local_cache_filename = "/artifacts/" + bootstrap_filename
    assert os.path.exists(local_cache_filename)
    log.info("Copying bootstrap out of cache")
    try:
        subprocess.check_output(['mkdir', '-p', '/genconf/serve/bootstrap/'])
        subprocess.check_output(['cp', local_cache_filename, save_path])
    except (KeyboardInterrupt, CalledProcessError) as ex:
        log.error("Copy failed or interrupted %s", ex.cmd)
        log.error("Failed commandoutput: %s", ex.output)
        cleanup_and_exit()


def main():
    parser = argparse.ArgumentParser(description="Generates DCOS configuration.")
    ssh_deployer = parser.add_mutually_exclusive_group()

    # Log level
    parser.add_argument(
        '-l',
        '--log-level',
        default='info',
        type=str,
        choices=['debug', 'info'],
        help='Log level. Info or debug')

    # Set interactive mode
    # NOTE: Only applies to genconf mode
    ssh_deployer.add_argument(
        '-i',
        '--interactive',
        action='store_true',
        default=False,
        help='Interactive configuration builder.')

    # NOTE: Only applies to deploy options (preflight, postflight, deploy, uninstall, etc)
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='No colored logs.')

    # Add an explicit genconf option for those who want it. The legacy behavior
    # when no arguments are given is maintained.
    ssh_deployer.add_argument(
        '--genconf',
        action='store_true',
        help='Generate configuration files for DCOS installation.')

    # Set preflight flag
    ssh_deployer.add_argument(
        '--preflight',
        action='store_true',
        help='Execute preflight on target DCOS hosts.')

    # Set deploy flag
    ssh_deployer.add_argument(
        '--deploy',
        action='store_true',
        help='Install DCOS on target DCOS hosts.')

    # Set postflight flag
    ssh_deployer.add_argument(
        '--postflight',
        action='store_true',
        help='Execute the post-flight on target DCOS hosts.')

    # Clean flag
    ssh_deployer.add_argument(
        '--uninstall',
        action='store_true',
        help='Uninstall DCOS on target DCOS hosts.')

    # Parse the arguments and dispatch.
    options = parser.parse_args()
    if options.log_level == "debug":
        log.basicConfig(level=log.DEBUG)
        log.debug("Log level set to DEBUG")
    elif options.log_level == "info":
        log.basicConfig(level=log.INFO)
        log.info("Log level set to INFO")
    else:
        log.error("Logging option not available: %s", options.log_level)
        sys.exit(1)

    if not options.no_color:
        from deploy.pretty_log import colored_log
        colored_log(options.log_level)

    if options.genconf:
        do_genconf(options)
        sys.exit(0)

    if options.preflight:
        _, config = get_config(options)
        run_preflight(config)
        sys.exit(0)

    if options.deploy:
        _, config = get_config(options)
        install_dcos(config)
        sys.exit(0)

    if options.postflight:
        _, config = get_config(options)
        run_postflight(config)
        sys.exit(0)

    if options.uninstall:
        _, config = get_config(options)
        uninstall_dcos(config)
        sys.exit(0)

    # Fallback behavior when no explicit action flag is given, run genconf
    # since that is what used to happen.
    do_genconf(options)
    sys.exit(0)


if __name__ == '__main__':
    main()
