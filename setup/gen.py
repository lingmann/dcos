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
import importlib
import jinja2
import jinja2.meta
import json
import os
import os.path
import sys
import urllib.request
import yaml
from math import floor
from pkgpanda.build import hash_checkout
from pkgpanda.util import make_tar
from tempfile import TemporaryDirectory


# List of all roles all templates should have.
current_roles = {"master", "slave", "public_slave", "master_slave"}

# The set of supported providers and distributions.
providers = ['vagrant', 'aws', 'gce', 'azure',  'on_prem']
distributions = ['coreos', 'jessie', 'centos7']

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.getcwd()),
        undefined=jinja2.StrictUndefined)


def render_yaml(data):
    return yaml.dump(data, default_style='|', default_flow_style=False)


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


# Order in a file determines order in which things like services get placed,
# changing it can break components (Ex: moving dcos-download and dcos-setup
# too early will break some configurations).
def get_filenames(provider, distribution, target):
    return [
        target,
        distribution + '/' + target,
        provider + '/' + target,
        distribution + '-' + provider + '/' + target]


# Returns a dictionary of the jinja templates to use
def get_template_names(provider, distribution):
    return {
        # Contains core DCOS service configuration, updated always via pkgpanda.
        # Order is important for running bits properly
        "dcos-config--setup":
            get_filenames(provider, distribution, 'dcos-config.yaml'),
        # Cloud config contains the per-host configuration configured by the
        # provider, as well as provider-specific config packages which depend on
        # initial launch parameters. All files entries, services should be
        # updated via system config managers. The dcos-config-{provider} package
        # should be updated via pkgpanda.
        "cloud-config":
            get_filenames(provider, distribution, 'cloud-config.yaml')
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


def add_set(lhs, rhs):
    return set(lhs) | set(rhs)


# Load all the un-bound variables in the templates which need to be given values
# in order to convert the templates to go from jinja -> yaml. These are
# effectively the set of DCOS parameters.
def get_parameters(provider, distribution, templates):
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

    # Load any additional parameters
    parameters |= load_json_list(
            get_filenames(provider, distribution, "parameters.json"),
            add_set)

    return parameters


def update_dictionary(base, addition):
    base_copy = base.copy()
    base_copy.update(addition)
    return base_copy


# TODO(cmaloney): Do a recursive dictionary merge
def load_arguments(provider, distribution, config):
    # Order is important for overriding
    arguments = load_json_list(
            get_filenames(provider, distribution, 'arguments.json'),
            merge_dictionaries)

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
    return load_json_list(
            get_filenames(provider, distribution, 'defaults.json'),
            update_dictionary)


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
    parser.add_argument('provider', choices=providers)
    parser.add_argument('distribution', choices=distributions)
    parser.add_argument(
            '-c',
            '--config',
            type=str,
            help='JSON configuration file to load')
    parser.add_argument('--assume-defaults', action='store_true')
    parser.add_argument('--save-config', type=str)
    args = parser.parse_args()

    provider = importlib.import_module(args.provider)

    # Load the templates for the target and figure out mandatory parameters.
    templates = get_template_names(args.provider, args.distribution)
    parameters = get_parameters(args.provider, args.distribution, templates)

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

    # Prompt user to provide all unset arguments. If a config file was specified
    # output
    user_arguments = {}
    for name in to_set:
        while True:
            if args.assume_defaults and name in defaults:
                user_arguments[name] = defaults[name]
                break

            # TODO(cmaloney): If 'config only' is set never prompt.
            default_str = ' [{}]'.format(defaults[name]) if name in defaults else ''
            value = input('{}{}: '.format(name, default_str))
            if value:
                user_arguments[name] = value
                break
            if name in defaults:
                user_arguments[name] = defaults[name]
                break
            print("ERROR: Must provide a value")

    # TODO(cmaloney): Error If non-interactive and not all arguments are set.
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

    # TODO(cmaloney): add a mechanism for individual components to compute more
    # arguments here and fill in.

    # Validate that all parameters have been set
    assert(parameters - arguments.keys() == set())

    print("Final arguments:")
    print(json.dumps(arguments, sort_keys=True, indent=2))

    # ID of this configuration is a hash of the parameters
    config_id = hash_checkout(arguments)

    config_package_id = "dcos-config--setup-{}".format(config_id)

    # This isn't included in the 'final arguments', but it is computable from it
    # so this isn't a "new" argument, just a "derived" argument.
    arguments['config_package_id'] = config_package_id
    config_package_filename = config_package_id + '.tar.xz'

    # Save config parameters
    if args.save_config:
        write_json(args.save_config, arguments)
        print("Config saved to:", args.save_config)

    # Fill in the template parameters
    rendered_templates = render_templates(templates, arguments)

    # There is only the dcos-config--setup and cloud-config templates
    assert set(rendered_templates.keys()) == set(["cloud-config", "dcos-config--setup"])

    # Get out the cloud-config text for use in provider-specific templates
    # Cloud config must start with #cloud-config so prepend the name
    # to the start of the YAML
    cloud_config = "#cloud-config\n" + \
        render_yaml(rendered_templates['cloud-config'])

    config_package_filename = "dcos-config--setup-{}.tar.xz".format(config_id)
    # Generate the specific dcos-config package.
    # Version will be setup-{sha1 of contents}
    with TemporaryDirectory("dcos-config--setup") as tmpdir:
        dcos_setup = rendered_templates['dcos-config--setup']

        # Only contains write_files
        assert len(dcos_setup) == 1

        # Write out the individual files
        for file_info in dcos_setup["write_files"]:
            path = tmpdir + file_info['path']
            try:
                os.makedirs(os.path.dirname(path), mode=0o755)
            except FileExistsError:
                pass

            with open(path, 'w') as f:
                f.write(file_info['content'])

        make_tar(config_package_filename, tmpdir)

    print("Config package filename: ", config_package_filename)

    provider.gen(cloud_config, config_package_filename, arguments)
