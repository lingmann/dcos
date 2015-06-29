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
import collections
import importlib
import jinja2
import jinja2.meta
import json
import os
import os.path
import sys
import yaml
from copy import deepcopy
from pkgpanda import PackageId
from pkgpanda.build import hash_checkout
from pkgpanda.util import make_tar, write_string
from tempfile import TemporaryDirectory

# List of all roles all templates should have.
role_names = {"master", "slave", "public_slave", "master_slave"}

# The set of supported providers and distributions.
providers = ['vagrant', 'aws', 'gce', 'azure',  'on_prem']
distributions = ['coreos', 'jessie', 'centos7']

role_template = '/etc/mesosphere/roles/{}'

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.getcwd()),
        undefined=jinja2.StrictUndefined)


def add_roles(cloudconfig, roles):
    for role in roles:
        cloudconfig['write_files'].append({
            "path": role_template.format(role),
            "content": ""
            })

    return cloudconfig


def add_units(cloudconfig, services):
    cloudconfig['coreos']['units'] += services
    return cloudconfig


# For converting util -> a namespace only.
class Bunch(object):

    def __init__(self, adict):
        self.__dict__.update(adict)


def render_cloudconfig(data):
    return "#cloud-config\n" + render_yaml(data)


utils = Bunch({
    "role_template": role_template,
    "add_roles": add_roles,
    "role_names": role_names,
    "add_services": None,
    "add_units": add_units,
    "render_cloudconfig": render_cloudconfig
})


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
    templates = dict()
    # dcos-config contains stuff statically known for clusters (ex: mesos slave
    # configuration parametesr).
    # cloud-config contains things injected per-cluster by tools such as
    # cloudformation. Ex: AWS S3 bucket to use for Exhibitor,
    # master loadbalancer DNS name
    for template in ['dcos-config', 'cloud-config', 'dcos-services']:
        templates[template] = get_filenames(provider, distribution, template + '.yaml')
    return templates


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
            print("ERROR: Specified config file '" + config + "' does not exist")
            sys.exit(1)
        except ValueError as ex:
            print("ERROR:", ex.what())
            sys.exit(1)

    return arguments


def load_default_arguments(provider, distribution):
    return load_json_list(
            get_filenames(provider, distribution, 'defaults.json'),
            update_dictionary)


def load_calculations(provider, distribution):
    all_names = set()
    must_fn = {}
    can_fn = {}
    validate_fn = []
    for modulename in get_filenames(provider, distribution, 'calc'):
        try:
            module = importlib.import_module(modulename)
        except ImportError:
            break

        # Can't calculate the same thing twice.
        names = module.must.keys() | module.can.keys()
        for name in names:
            if name in all_names:
                raise AssertionError("ERROR: Multiple ways to calculate", name, "one is in", modulename)

        all_names |= names

        must_fn.update(module.must)
        can_fn.update(module.can)
        try:
            validate_fn.append(module.validate)
        except AttributeError:
            pass

    return must_fn, can_fn, validate_Fn


class LazyArgumentCalculator(collections.Mapping):

    def __init__(self, must_fn, can_fn, arguments):
        self._calculators = must_fn
        self._calculators.update(can_fn)
        self._arguments = arguments
        self.__in_progress = set()

    def __getitem__(self, name):
        if name in self._arguments:
            return self._arguments[name]

        # Detect cycles by checking if we're in the middle of calculating the
        # argument being asked for
        if name in self.__in_progress:
            raise AssertionError("Cycle detected. Encountered {}".format(name))

        try:
            self.__in_progress.add(name)
            self._arguments[name] = self._calculators[name](self)
        except AssertionError as ex:
            raise AssertionError(str(ex) + " while calculating {}".format(name)) from ex
        return self._arguments[name]

    def __iter__(self):
        raise NotImplementedError()

    def __len__(self):
        return len(self._arguments)

    def get_arguments(self):
        return self._arguments


def calculate_args(must_fn, can_fn, arguments):
    start_arguments = deepcopy(arguments)

    # Build the argument dictionary
    arg_calculator = LazyArgumentCalculator(must_fn, can_fn, arguments)

    # Force calculation of all arguments by accessing
    for key in must_fn.keys():
        if key in start_arguments:
            raise AssertionError("Argument which must be calculated '", key, "' manually specified in arguments")

        arg_calculator[key]

    # Force calculation of optional arguments.
    # Seperated from mandatory ones since we just pass on pre-specified
    for key in can_fn.keys():
        if key in start_arguments:
            pass

        arg_calculator[key]

    return arg_calculator.get_arguments()


def validate_args(arguments):


json_prettyprint_args = {
    "sort_keys": True,
    "indent": 2,
    "separators": (',', ':')
}


def write_json(filename, data):
    with open(filename, "w+") as f:
        return json.dump(data, f, **json_prettyprint_args)


def write_to_non_taken(base_filename, json):
    number = 0

    filename = base_filename
    while (os.path.exists(filename)):
        number += 1
        filename = base_filename + '.{}'.format(number)

    write_json(filename, json)

    return filename


def add_arguments(parser):
    parser.add_argument('--config',
                        type=str,
                        help='JSON configuration file to load')
    parser.add_argument('--assume-defaults', action='store_true')
    parser.add_argument('--save-config', type=str)

    return parser


def main():
    # Get basic arguments from user.
    parser = argparse.ArgumentParser(
            description='Generate config for a DCOS environment')
    parser = add_arguments(parser)
    args = parser.parse_args()

    provider = importlib.import_module(args.provider)

    # Load the templates for the target and figure out mandatory parameters.
    templates = get_template_names(args.provider, args.distribution)
    parameters = get_parameters(args.provider, args.distribution, templates)

    # Load the arguments provided by the provider, distro, and user.
    arguments = load_arguments(args.provider, args.distribution, args.config)

    # Load default arguments
    defaults = load_default_arguments(args.provider, args.distribution)

    # Calculate the set of parameters which still need to be input.
    to_set = parameters - arguments.keys()

    # Load what we can calculate
    # TODO(cmaloney): Merge extra arguments, defaults into calc?
    must_calc, can_calc, validate_fn = load_calculations(args.provider, args.distribution)

    # Remove calculated parameters from those to calculate.
    to_set -= must_calc.keys()
    to_set -= can_calc.keys()

    # Cluster packages is particularly magic
    # as it depends on the config filename which depends on the initial set
    # of arguments.
    to_set.remove('cluster_packages')

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

            default_str = ''
            if name in defaults:
                default_str = ' [{}]'.format(defaults[name])
            elif name in can_calc:
                default_str = ' (can calculated)'

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

    if 'resolvers' in arguments:
        assert isinstance(arguments['resolvers'], list)
        arguments['resolvers'] = json.dumps(arguments['resolvers'])

    # Set arguments from command line flags.
    arguments['provider'] = args.provider
    arguments['distribution'] = args.distribution

    # Calculate the remaining arguments.
    arguments = calculate_args(must_calc, can_calc, arguments)

    # Validate arguments.
    # TODO(cmaloney): Define an API for allowing multiple failures, reporting
    # more than just the first error.
    for fn in validate_fn:
        fn(arguments)

    print("Final arguments:")
    print(json.dumps(arguments, **json_prettyprint_args))

    # ID of this configuration is a hash of the parameters
    config_id = hash_checkout(arguments)

    config_package_id = "dcos-config--setup_{}".format(config_id)

    # This isn't included in the 'final arguments', but it is computable from it
    # so this isn't a "new" argument, just a "derived" argument.
    arguments['config_package_id'] = config_package_id
    # Validate the PackageId conforms to the rules.
    PackageId(config_package_id)

    config_package_filename = config_package_id + '.tar.xz'
    arguments['config_package_filename'] = config_package_filename
    # NOTE: Not pretty-printed to make it easier to drop into YAML as a one-liner
    arguments['cluster_packages'] = json.dumps([config_package_id])

    # Save config parameters
    if args.save_config:
        write_json(args.save_config, arguments)
        print("Config saved to:", args.save_config)

    # Fill in the template parameters
    rendered_templates = render_templates(templates, arguments)

    # Hard fail if more templates are added. Each new template needs code added
    # below to deal with its output.
    assert set(rendered_templates.keys()) == set(["cloud-config", "dcos-config", "dcos-services"])

    # Get out the cloud-config text for use in provider-specific templates
    # Cloud config must start with #cloud-config so prepend the name
    # to the start of the YAML
    cloud_config = rendered_templates['cloud-config']

    # Generate the specific dcos-config package.
    # Version will be setup-{sha1 of contents}
    with TemporaryDirectory("dcos-config--setup") as tmpdir:
        dcos_setup = rendered_templates['dcos-config']

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
    write_string("dcos-config.latest", config_package_id)

    # Add in the add_services util. Done here instead of the initial
    # map since we need to bind in parameters
    def add_services(cloudconfig):
        return add_units(cloudconfig, rendered_templates['dcos-services'])

    utils.add_services = add_services

    provider.gen(cloud_config, arguments, utils)

if __name__ == "__main__":
    try:
        main()
    except jinja2.TemplateSyntaxError as ex:
        print("ERROR: Jinja2 TemplateSyntaxError")
        print("{}:{} - {}".format(
            ex.filename if ex.filename else (ex.name if ex.name else '<>'),
            ex.lineno,
            ex.message))
        sys.exit(1)
