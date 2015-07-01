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

import collections
import importlib
import jinja2
import jinja2.meta
import json
import os
import os.path
import sys
import yaml
from copy import copy, deepcopy
from pkgpanda import PackageId
from pkgpanda.build import hash_checkout
from pkgpanda.util import make_tar
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


# Order in a file determines order in which things like services get placed,
# changing it can break components (Ex: moving dcos-download and dcos-setup
# too early will break some configurations).
def get_filenames(mixins, target, sep='/'):
    return ['gen' + sep + target] + ['gen' + sep + mixin + sep + target for mixin in mixins]


# Returns a dictionary of the jinja templates to use
def get_template_names(mixins):
    templates = dict()
    # dcos-config contains stuff statically known for clusters (ex: mesos slave
    # configuration parametesr).
    # cloud-config contains things injected per-cluster by tools such as
    # cloudformation. Ex: AWS S3 bucket to use for Exhibitor,
    # master loadbalancer DNS name
    for template in ['dcos-config', 'cloud-config', 'dcos-services']:
        templates[template] = get_filenames(mixins, template + '.yaml')
    return templates


# Render the Jinja/YAML into YAML, then load the YAML and merge it to make the
# final configuration files.
def render_templates(template_names, arguments):
    rendered_templates = dict()
    for name, templates in template_names.items():
        full_template = None
        for template in templates:
            if not os.path.exists(template):
                continue

            rendered_template = env.get_template(template).render(arguments)

            # If not yaml, just treat opaquely.
            if not template.endswith('.yaml'):
                # No merging support currently.
                assert len(templates) == 1
                full_template = rendered_template
                continue

            template_data = yaml.load(rendered_template)

            if full_template:
                full_template = merge_dictionaries(full_template, template_data)
            else:
                full_template = template_data

        rendered_templates[name] = full_template

    return rendered_templates


def add_set(lhs, rhs):
    return set(lhs) | set(rhs)


# Load all the un-bound variables in the templates which need to be given values
# in order to convert the templates to go from jinja -> yaml. These are
# effectively the set of DCOS parameters.
def get_parameters(templates):
    parameters = set()
    for templates in templates.values():
        if len(templates) > 1:
            for template in templates:
                assert template.endswith('.yaml')

        for template in templates:
            try:
                ast = env.parse(open(template).read())
                template_parameters = jinja2.meta.find_undeclared_variables(ast)
                parameters |= set(template_parameters)
            except FileNotFoundError as ex:
                print("NOTICE: not found:", ex)

    return parameters


def update_dictionary(base, addition):
    base_copy = base.copy()
    base_copy.update(addition)
    return base_copy


class LazyArgumentCalculator(collections.Mapping):

    def __init__(self, must_fn, can_fn, arguments):
        self._calculators = deepcopy(must_fn)
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
            print(must_fn[key])
            raise AssertionError("Argument which must be calculated '", key, "' manually specified in arguments")

        arg_calculator[key]

    # Force calculation of optional arguments.
    # Seperated from mandatory ones since we just pass on pre-specified
    for key in can_fn.keys():
        if key in start_arguments:
            pass

        arg_calculator[key]

    return arg_calculator.get_arguments()


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
    parser.add_argument('--non-interactive', action='store_true')

    return parser


def get_options_object():
    return Bunch({
        'config': None,
        'assume_defaults': True,
        'save_config': None,
        'non_interactive': True
        })


def do_package_config(config, config_package_filename):
    # Generate the specific dcos-config package.
    # Version will be setup-{sha1 of contents}
    with TemporaryDirectory("dcos-config--setup") as tmpdir:
        dcos_setup = config

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


def load_mixins(mixins):
    all_names = set()
    arguments = dict()
    can_fn = dict()
    defaults = dict()
    must_fn = dict()
    parameters = list()
    validate_fn = list()

    for modulename in get_filenames(mixins, 'calc', sep='.'):
        # Specifying all these is optional, as is having a module at all so we
        # wrap them all in try / catches to handle non-existence.
        try:
            module = importlib.import_module(modulename)
        except ImportError as ex:
            print("NOTICE: not found:".format(modulename), ex)
            break

        try:
            # Can't calculate the same thing twice.
            names = module.must.keys()
            for name in names:
                if name in all_names:
                    raise AssertionError("ERROR: Multiple ways to calculate", name, "one is in", modulename)
            all_names |= names
            must_fn.update(module.must)
        except AttributeError:
            pass

        try:
            # Can't calculate the same thing twice.
            names = module.can.keys()
            for name in names:
                if name in all_names:
                    raise AssertionError("ERROR: Multiple ways to calculate", name, "one is in", modulename)
            all_names |= names
            can_fn.update(module.can)
        except AttributeError:
            pass

        try:
            validate_fn.append(module.validate)
        except AttributeError:
            pass

        try:
            parameters += module.parameters
        except AttributeError:
            pass

        try:
            arguments = update_dictionary(arguments, module.arguments)
        except AttributeError:
            pass

        try:
            defaults = update_dictionary(defaults, module.defaults)
        except AttributeError:
            pass

    return Bunch({
        'arguments': arguments,
        'can_calc': can_fn,
        'defaults': defaults,
        'must_calc': must_fn,
        'validate_fn': validate_fn,
        'parameters': parameters
    })


def prompt_arguments(to_set, defaults, can_calc):
    arguments = dict()
    for name in sorted(to_set):
        while True:
            default_str = ''
            if name in defaults:
                default_str = ' [{}]'.format(defaults[name])
            elif name in can_calc:
                default_str = ' (can calculate)'

            # TODO(cmaloney): If 'config only' is set never prompt.
            default_str = ' [{}]'.format(defaults[name]) if name in defaults else ''
            value = input('{}{}: '.format(name, default_str))
            if value:
                arguments[name] = value
                break
            if name in defaults:
                arguments[name] = defaults[name]
                break
            print("ERROR: Must provide a value")

    return arguments


def do_generate(
        options,
        mixins,
        extra_templates,
        arguments):

    # Load the templates for the target and calculate the parameters based on
    # the template variables.
    templates = get_template_names(mixins)
    templates.update(extra_templates)
    parameters = get_parameters(templates)

    # Load information provided by mixins (parametesr that can be calculated,
    # defaults for some arguments, etc).
    mixin_helpers = load_mixins(mixins)
    must_calc = mixin_helpers.must_calc
    can_calc = mixin_helpers.can_calc
    validate_fn = mixin_helpers.validate_fn
    # TODO(cmaloney): Error if overriding.
    arguments.update(mixin_helpers.arguments)
    defaults = mixin_helpers.defaults
    parameters.update(mixin_helpers.parameters)

    # Load user specified arguments.
    # TODO(cmaloney): Repeating a set argument should be a hard error.
    if options.config:
        try:
            new_arguments = load_json(arguments.config)
            arguments.update(new_arguments)
        except FileNotFoundError:
            print("ERROR: Specified config file '" + arguments.config + "' does not exist")
            sys.exit(1)
        except ValueError as ex:
            print("ERROR:", ex.what())
            sys.exit(1)

    # Calculate the set of parameters which still need to be input.
    to_set = parameters - arguments.keys()

    # Remove calculated parameters from those to calculate.
    to_set -= must_calc.keys()
    to_set -= can_calc.keys()

    # If assume_defaults, apply all defaults
    if options.assume_defaults:
        for name in copy(to_set):
            if name in defaults:
                arguments[name] = defaults[name]
                to_set.remove(name)

    # Cluster packages is particularly magic
    # as it depends on the config filename which depends on the initial set
    # of arguments.
    to_set.remove('cluster_packages')

    # Prompt user to provide all unset arguments. If a config file was specified
    # output
    if options.non_interactive:
        if len(to_set) > 0:
            print("ERROR: Unset variables when run in interactive mode:", ','.join(to_set))
            sys.exit(1)
    else:
        user_arguments = prompt_arguments(to_set, defaults, can_calc)
        arguments = update_dictionary(arguments, user_arguments)

    if 'resolvers' in arguments:
        assert isinstance(arguments['resolvers'], list)
        arguments['resolvers'] = json.dumps(arguments['resolvers'])

    # Set arguments from command line flags.
    arguments['mixins'] = mixins

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
    if options.save_config:
        write_json(options.save_config, arguments)
        print("Config saved to:", options.save_config)

    # Fill in the template parameters
    rendered_templates = render_templates(templates, arguments)

    do_package_config(rendered_templates['dcos-config'], config_package_filename)

    # Add in the add_services util. Done here instead of the initial
    # map since we need to bind in parameters
    def add_services(cloudconfig):
        return add_units(cloudconfig, rendered_templates['dcos-services'])

    utils.add_services = add_services

    return Bunch({
        'arguments': arguments,
        'config_package_id': config_package_id,
        'templates': rendered_templates,
        'utils': utils
    })


def generate(
        options,
        mixins,
        extra_templates=dict(),
        arguments=dict()):
    try:
        return do_generate(options, mixins, extra_templates, arguments)
    except jinja2.TemplateSyntaxError as ex:
        print("ERROR: Jinja2 TemplateSyntaxError")
        print("{}:{} - {}".format(
            ex.filename if ex.filename else (ex.name if ex.name else '<>'),
            ex.lineno,
            ex.message))
        sys.exit(1)
