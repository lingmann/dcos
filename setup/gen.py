#!/usr/bin/env python3
"""Framework for creating data for provider-specific templates.

Parameterizes on two levels
1. Target end platform / Distribution method
    - AWS, GCE, Azure, Puppet, Chef, Ansible, Salt, Vagrant, DCOS, Docker,
      Standalone
2. Target OS
    - CoreOS, CentOS, RHEL, Debian, Ubuntu


NOTE:
    - Not all combos make sense / would be used. Only whitelist / enable ones we
      have people on.
"""

import argparse
import jinja2
import jinja2.meta
import json
import os
import sys
import urllib.request
import yaml
from math import floor

# List of all roles all templates should have.
current_roles = {"master", "slave", "public_slave", "master_slave"}

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.getcwd()),
        undefined=jinja2.StrictUndefined)


# Recursively merge to python dictionaries.
# If both base and addition contain the same key, that key's value will be
# merged if it is a dictionary.
# This is unlike the python dict.update() method which just overwrites matching
# keys.
def merge_dictionaries(base, additions):
    base_copy = base.copy()
    for k, v in additions.items():
        try:
            if k not in base:
                base_copy[k] = v
                continue
            if isinstance(v, dict) and isinstance(base_copy[k], dict):
                base_copy[k] = merge_dictionaries(base_copy.get(k, dict()), v)
                continue

            # Append arrays
            if isinstance(v, list) and isinstance(base_copy[k], list):
                base_copy[k].extend(v)
                continue

            # Unknwon types
            raise ValueError("Can't merge type {} into type {}".format(type(v), type(base_copy[k])))
        except ValueError as ex:
            raise ValueError("{} inside key {}".format(ex, k)) from ex
    return base_copy


# Returns a dictionary of the jinja templates to use
def get_template_names(provider, distribution):
    # Order in a file determines order in which things like services get placed,
    # changing it can break components (Ex: moving dcos-download and dcos-setup
    # too early will break some configurations).
    return {
        # Contains core DCOS service configuration, updated always via pkgpanda.
        # Order is important for running bits properly
        "dcos-config--setup": [
            "dcos-config.yaml",
            "dcos-config-" + distribution + '.yaml',
            "dcos-config-" + provider + '.yaml',
            "dcos-config-" + distribution + '-' + provider + '.yaml',
        ],
        # Cloud config contains the per-host configuration configured by the
        # provider, as well as provider-specific config packages which depend on
        # initial launch parameters. All files entries, services should be
        # updated via system config managers. The dcos-config-{provider} package
        # should be updated via pkgpanda.
        "cloud-config": [
            distribution + '.yaml',
            provider + '.yaml',
            distribution + '-' + provider + '.yaml',
            "cloud-config.yaml"
        ]
    }


# Render the Jinja/YAML into YAML, then load the YAML and merge it to make the
# final configuration files.
def render_templates(template_names, arguments):
    rendered_templates = dict()
    for name, templates in template_names.items():
        loaded_yaml = None
        for template in templates:
            if not os.path.exists(template):
                continue

            yaml_str = env.get_template(template).render(arguments)
            template_data = yaml.load(yaml_str)

            if loaded_yaml:
                loaded_yaml = merge_dictionaries(loaded_yaml, template_data)
            else:
                loaded_yaml = template_data

        rendered_templates[name] = loaded_yaml

    return rendered_templates


# Load all the un-bound variables in the templates which need to be given values
# in order to convert the templates to go from jinja -> yaml. These are
# effectively the set of DCOS parameters.
def get_parameters(templates):
    parameters = set()
    for name, templates in templates.items():
        for template in templates:
            assert template.endswith('.yaml')
            if not os.path.exists(template):
                # print("NOTICE: not found", template)
                continue
            # TODO(cmaloney): Organize parameters based on where they came from.
            ast = env.parse(open(template).read())
            template_parameters = jinja2.meta.find_undeclared_variables(ast)
            parameters |= set(template_parameters)

    return parameters


def load_json(filename):
    try:
        with open(filename) as f:
            return json.load(f)
    except ValueError as ex:
        raise ValueError("Invalid JSON in {0}: {1}".format(filename, ex)) from ex


def load_json_list(filenames, merge_func):
    result = {}
    # Update with all arguments
    for filename in filenames:
        # TODO(cmaloney): Make sure no arguments are overwritten / this only
        # adds arguments.
        try:
            new_result = load_json(filename)
            result = merge_func(result, new_result)
        except FileNotFoundError:
            # print("NOTICE: not found", filename)
            pass

    return result


def update_dictionary(base, addition):
    base_copy = base.copy()
    base_copy.update(addition)
    return base_copy


# TODO(cmaloney): Do a recursive dictionary merge
def load_arguments(provider, distribution, config):
    # Order is important for overriding
    files_to_load = [
        provider + '.json',
        distribution + '.json',
        distribution + '-' + provider + '.json',
    ]
    arguments = load_json_list(files_to_load, merge_dictionaries)

    # Load the config if it was specified. Seperate from the other options
    # because it not existing is a hard error.
    if config:
        try:
            new_arguments = load_json(config)
            arguments.update(new_arguments)
        except FileNotFoundError:
            print("ERROR: Specified config file '", config, "' does not exist")
            sys.exit(1)
        except ValueError as ex:
            print("ERROR:", ex.what())
            sys.exit(1)

    return arguments


def load_default_arguments(provider, distribution):
    # Order is important for overriding
    files_to_load = [
        'defaults.json',
        provider + '.defaults.json',
        distribution + '.defaults.json',
        distribution + '.' + provider + '.defaults.json',
    ]
    return load_json_list(files_to_load, update_dictionary)


def write_json(filename, data):
    with open(filename, "w+") as f:
        return json.dump(data, f, sort_keys=True, indent=2, seperators=(',', ':'))


def write_to_non_taken(base_filename, json):
    number = 0

    filename = base_filename
    while (os.path.exists(filename)):
        number += 1
        filename = base_filename + '.{}'.format(number)

    write_json(filename, json)

    return filename

if __name__ == "__main__":
    # Get basic arguments from user.
    parser = argparse.ArgumentParser(
            description='Generate config for a DCOS environment')
    parser.add_argument('provider', choices=['aws', 'gce', 'azure',  'on_prem'])
    parser.add_argument('distribution', choices=['coreos', 'jessie', 'centos7'])
    parser.add_argument(
            '-c',
            '--config',
            type=str,
            help='JSON configuration file to load')
    args = parser.parse_args()

    # Load the templates for the target and figure out mandatory parameters.
    templates = get_template_names(args.provider, args.distribution)
    parameters = get_parameters(templates)

    # Filter out generated parameters
    parameters.remove('master_quorum')
    parameters.remove('bootstrap_url')
    parameters.add('release_name')

    # Load the arguments provided by the provider, distro, and user.
    arguments = load_arguments(args.provider, args.distribution, args.config)

    # Load default arguments
    defaults = load_default_arguments(args.provider, args.distribution)

    # Calculate the set of parameters which still need to be input.
    to_set = parameters - arguments.keys()

    # TODO(cmaloney): If in strict mode and some arguments aren't used, error
    # and exit.

    # TODO(cmaloney): If config-only + 'use defaults' is set then load the
    # defaults into the arguments for anything not set.

    # TODO(cmaloney): If no-prompt / config-only error if not all parameters are
    # set.

    # Prompt user to provide all unset arguments. If a config file was specified
    # output
    user_arguments = {}
    for name in to_set:
        while True:
            default_str = ' [{}]'.format(defaults[name]) if name in defaults else ''
            value = input('{}{}: '.format(name, default_str))
            if value:
                user_arguments[name] = value
                break
            if name in defaults:
                user_arguments[name] = defaults[name]
                break
            print("ERROR: Must provide a value")

    arguments = update_dictionary(arguments, user_arguments)

    # TODO(cmaloney): Validate basic arguments
    assert(int(arguments['num_masters']) in [1, 3, 5, 7, 9])
    # Calculate and set master_quorum based on num_masters
    arguments['master_quorum'] = floor(int(arguments['num_masters']) / 2 + 1)

    if arguments['bootstrap_id'] == 'automatic':
        url = 'http://downloads.mesosphere.com/dcos/{}/bootstrap.latest'.format(arguments['release_name'])
        arguments['bootstrap_id'] = urllib.request.urlopen(url).read().decode('utf-8')

    if 'bootstrap_url' not in arguments:
        arguments['bootstrap_url'] = 'http://downloads.mesosphere.com/dcos/{}'.format(arguments['release_name'])
    else:
        # Needs to conflict with certain combinations of bootstrap_id and release_name
        raise NotImplementedError()

    # Validate that all parameters have been set
    assert(parameters - arguments.keys() == set())

    print("Final parameters:")
    print(json.dumps(arguments, sort_keys=True, indent=2))

    # Save config parameters
    #final_config_filename = write_to_non_taken("config-result.json", arguments)
    #print("Config saved to:", final_config_filename)

    # Fill in the template parameters
    rendered_templates = render_templates(templates, arguments)

    # Render dcos-config--setup template into a tarball with user-specific data.
    for name, data in rendered_templates.items():
        print("#" + name)
        print(yaml.dump(data, default_flow_style=False))

    # TODO(cmaloney): Get provider-specific templates and render them (Ex:
    # cloud-formation templates with embedded cloud-config)
