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
import logging as log
from copy import copy, deepcopy
from itertools import chain
from pkgpanda import PackageId
from pkgpanda.build import hash_checkout
from pkgpanda.util import make_tar
from subprocess import check_call
from tempfile import TemporaryDirectory

# List of all roles all templates should have.
role_names = {"master", "slave", "slave_public"}

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
def get_name(mixin_name, target, sep='/'):
    if mixin_name:
        return 'gen' + sep + mixin_name + sep + target
    else:
        return 'gen' + sep + target


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


# Load all the un-bound variables in the templates which need to be given values
# in order to convert the templates to go from jinja -> final template. These
# are effectively the set of DCOS parameters.
def get_parameters(template_dict):
    parameters = set()
    for template_list in template_dict.values():
        assert isinstance(template_list, list)
        for template in template_list:
            assert isinstance(template, str)
            try:
                ast = env.parse(open(template).read())
                template_parameters = jinja2.meta.find_undeclared_variables(ast)
                parameters |= set(template_parameters)
            except FileNotFoundError as ex:
                # Needs to be implemented with a logger
                log.debug("Template not found: %s", ex)

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
    parser.add_argument('--save-final-config', type=str)
    parser.add_argument('--save-user-config', type=str)
    parser.add_argument('--non-interactive', action='store_true')
    parser.add_argument('-l','--log-level', default='info', choices=['debug', 'info'], help='Logging level. Default: info. Options: info, debug.')

    return parser


def get_options_object():
    return Bunch({
        'config': None,
        'assume_defaults': True,
        'save_user_config': None,
        'save_final_config': None,
        'non_interactive': True,
        'log_level': 'info',
        })


def do_gen_package(config, package_filename):
    # Generate the specific dcos-config package.
    # Version will be setup-{sha1 of contents}
    # Forcibly set umask so that os.makedirs() always makes directories with
    # uniform permissions
    os.umask(0o000)

    with TemporaryDirectory("gen_tmp_pkg") as tmpdir:

        # Only contains write_files
        assert len(config) == 1

        # Write out the individual files
        for file_info in config["write_files"]:
            if file_info['path'][0] == '/':
                path = tmpdir + file_info['path']
            else:
                path = tmpdir + '/' + file_info['path']
            try:
                if os.path.dirname(path):
                    os.makedirs(os.path.dirname(path), mode=0o755)
            except FileExistsError:
                pass

            with open(path, 'w') as f:
                f.write(file_info['content'])

            # the file has special mode defined, handle that.
            if 'mode' in file_info:
                os.chmod(path, int(str(file_info['mode']), 8))
            else:
                os.chmod(path, 0o644)

        # Ensure the output directory exists
        if os.path.dirname(package_filename):
            os.makedirs(os.path.dirname(package_filename), exist_ok=True)

        # Make the package top level directory readable by users other than the owner (root).
        check_call(['chmod', 'go+rx', tmpdir])

        make_tar(package_filename, tmpdir)

    print("Package filename: ", package_filename)


def prompt_argument(non_interactive, name, can_calc=False, default=None, possible_values=None):
    if non_interactive:
        print("ERROR: Unset variable when run in non-interactive mode:", name)
        sys.exit(1)

    while True:
        default_str = ''
        if default is not None:
            # Validate default
            if possible_values is not None:
                assert default in possible_values
            default_str = ' [{}]'.format(default)
        elif can_calc:
            default_str = ' <calculated>'

        # Print key to desired input with possible defaults and type to be asserted
        possible_values_str = ''
        if possible_values:
          possible_values_str = '{' + ",".join(possible_values) + '}'

        descriptions = load_json("gen/descriptions.json")

        if name in descriptions:
          print("")
          print("[%s]"% name)
          print(descriptions[name])

        value = input('{}{}{}: '.format(name, default_str, possible_values_str))

        # Make sure value is one of the allowed values
        if possible_values is not None and value not in possible_values:
            print("ERROR: Value not one of the possible values:", ','.join(possible_values))
            continue

        if value:
            return value
        if default:
            return default
        if can_calc:
            return None

        print("ERROR: Must provide a value")


def prompt_arguments(non_interactive, to_set, defaults, can_calc):
    if non_interactive and len(to_set) > 0:
        print("ERROR: Unset variables when run in interactive mode:", ','.join(to_set))
        sys.exit(1)

    arguments = dict()
    for name in sorted(to_set):
        result = prompt_argument(non_interactive, name, name in can_calc, defaults.get(name))

        # Only if we got a value (Shouldn't calculate), set the argument.
        if result is not None:
            arguments[name] = result

    return arguments


# Returns a dictionary of the jinja templates to use
def get_templates(mixin_name, cluster_packages, core_templates):
    templates = dict()
    # dcos-config contains stuff statically known for clusters (ex: mesos slave
    # configuration parameters).
    # cloud-config contains things injected per-cluster by tools such as
    # cloudformation. Ex: AWS S3 bucket to use for Exhibitor,
    # master loadbalancer DNS name3
    for template in chain(cluster_packages, core_templates):
        # Stored as list for easier later processing / dictionary merging.
        templates[template] = [get_name(mixin_name, template + '.yaml')]

    return templates


class Mixin:

    def __init__(self, name, cluster_packages, core_templates):
        self.name = name
        self.templates = get_templates(name, cluster_packages, core_templates)
        self.parameters = get_parameters(self.templates)

        # Module for loading functions to calculate, validate arguments as well as defaults.
        self.modulename = get_name(name, 'calc', sep='.')
        # Merge calc into the base portions.

        # Specifying all these is optional, as is having a module at all so we
        # wrap them all in try / catches to handle non-existence, and give them all
        # empty defaults of the right type to handle early-exit.
        self.arguments = dict()
        self.can_fn = dict()
        self.defaults = dict()
        self.must_fn = dict()
        self.implies = dict()

        def no_validate(arguments):
            pass

        self.validate_fn = no_validate

        module = None
        # Load the library and grab things from it as seperate bits so we don't
        # catch the wrong exception by mistake.
        try:
            module = importlib.import_module(self.modulename)
        except ImportError as ex:
            log.debug("Module not found: %s", ex)

        if module:
            try:
                self.must_fn = module.must
            except AttributeError:
                pass

            try:
                self.can_fn = module.can
            except AttributeError:
                pass

            try:
                self.validate_fn = module.validate
            except AttributeError:
                pass

            try:
                # Updating rather than just assigning since many parameters are
                # derived from the templates already
                self.parameters |= set(module.parameters)
            except AttributeError:
                pass

            try:
                self.arguments = module.arguments
            except AttributeError:
                pass

            try:
                self.defaults = module.defaults
            except AttributeError:
                pass

            try:
                self.implies = module.implies
            except AttributeError:
                pass


# Ensure arguments aren't given repeatedly.
# Can be once in the set: defaults, can_fn, must_fn
# Can be once in the set: arguments, must_fn
def ensure_no_repeated(mixin_objs):
    check_default_names = set()
    check_argument_names = set()

    def add_assert_duplicate(base_set, names):
        for name in names:
            if name in base_set:
                raise AssertionError("ERROR: Multiple ways to calculate", name, "one is in", mixin.name)
        base_set |= set(names)

    for mixin in mixin_objs:
        add_assert_duplicate(check_default_names, mixin.defaults.keys())
        add_assert_duplicate(check_default_names, mixin.can_fn.keys())

        add_assert_duplicate(check_argument_names, mixin.arguments.keys())
        add_assert_duplicate(check_argument_names, mixin.must_fn.keys())


def do_generate(
        options,
        mixins,
        extra_templates,
        arguments,
        extra_cluster_packages):
    assert isinstance(extra_cluster_packages, list)
    assert not isinstance(extra_cluster_packages, str)

    # TODO(cmaloney): Remove flattening and teach lower code to operate on list
    # of mixins.
    templates = dict()
    parameters = set()
    must_calc = dict()
    can_calc = dict()
    validate_fn = list()
    defaults = dict()

    # Load user specified arguments.
    # TODO(cmaloney): Repeating a set argument should be a hard error.
    if options.config:
        try:
            user_arguments = load_json(options.config)

            # Check a value always / only in computed configs to give a cleaner
            # message to users when they try just feeding a computed config back
            # into the generation library.
            if 'dcos_image_commit' in user_arguments:
                print("ERROR: The configuration saved by --save-config cannot be fed directly back as `--config`. "
                      "It is the full computed configuration used to flesh out the various templates, and contains "
                      "multiple derived / calculated values that are asserted to be calculated "
                      "(dcos_image_commit, master_quorum, etc.). All computed parameters need to be removed "
                      "before the saved config can be used.")
                sys.exit(1)

            # Make sure there are no overlaps between arguments and user_arguments.
            # TODO(cmaloney): Switch to a better dictionary diff here which will
            # show all the errors at once.
            for k in user_arguments.keys():
                if k in arguments.keys():
                    print("ERROR: User config contains option `{}` already ".format(k) +
                          "provided by caller of gen.generate()")
                    sys.exit(1)

            # update arguments with the user_arguments
            arguments.update(user_arguments)
        except FileNotFoundError:
            print("ERROR: Specified config file '" + options.config + "' does not exist")
            sys.exit(1)
        except ValueError as ex:
            print("ERROR:", ex)
            sys.exit(1)

    # Empty string (top level directory) is always implicitly included
    assert '' not in mixins
    assert None not in mixins

    cluster_packages = list(sorted(set(
        ['dcos-config', 'dcos-detect-ip', 'dcos-metadata']
        + extra_cluster_packages)))
    core_templates = ['cloud-config', 'dcos-services']

    # Add the empty mixin so we pick up top-level config.
    mixins.append('')

    mixin_objs = list()
    for mixin in mixins:
        mixin_objs.append(Mixin(mixin, cluster_packages, core_templates))

    # Ask / prompt about "implies", recursively until we've resolved all implies.
    mixins_to_visit = copy(mixin_objs)
    while len(mixins_to_visit) > 0:
        mixin_obj = mixins_to_visit.pop()
        if not mixin_obj.implies:
            continue

        # Expand implies, prompt for every choice the user hasn't provided in
        # user_arguments.
        for name, value in mixin_obj.implies.items():
            parameters.add(name)
            # Prompt if the user hasn't already chosen which option to use.
            if name not in arguments:
                arguments[name] = prompt_argument(
                        options.non_interactive,
                        name,
                        can_calc=False,
                        default=None,
                        possible_values=value.keys())
            choice = arguments[name]

            # If there is no mixin for the choice or the mixin has already been
            # loaded, skip it.
            mixin_name = value[choice]
            if mixin_name is None or mixin_name in mixins:
                continue

            # Add the mixin to the set to be visited
            mixins.append(mixin_name)
            new_mixin = Mixin(mixin_name, cluster_packages, core_templates)
            mixin_objs.append(new_mixin)
            mixins_to_visit.append(new_mixin)

    ensure_no_repeated(mixin_objs)

    for mixin in mixin_objs:
        templates = merge_dictionaries(templates, mixin.templates)
        parameters |= mixin.parameters
        must_calc.update(mixin.must_fn)
        can_calc.update(mixin.can_fn)
        validate_fn.append(mixin.validate_fn)
        arguments.update(mixin.arguments)
        defaults.update(mixin.defaults)

    # Make sure only yaml templates have more than one mixin providing them / are provided more than once.
    for name, template_list in templates.items():
        if len(template_list) > 1:
            for template in template_list:
                if not template.endswith('.yaml'):
                    print("ERROR: Only know how to merge YAML templates at this point in time. Can't merge template",
                          name, template_list)
                    sys.exit(1)

    # Inject extra_templates and parameters inside.
    templates.update(extra_templates)
    parameters |= get_parameters(extra_templates)

    # Validate all arguments passed in actually correspond to parameters to
    # prevent human typo errors.
    for argument in arguments:
        if argument not in parameters:
            print("ERROR: Argument '", argument, "' given but not in parameters:", ', '.join(parameters))
            sys.exit(1)

    # Calculate the set of parameters which still need to be input.
    to_set = parameters - arguments.keys()

    # Remove calculated parameters from those to calculate.
    to_set -= must_calc.keys()

    # If assume_defaults, apply all defaults and calculated values.
    if options.assume_defaults:
        for name in copy(to_set):
            if name in defaults:
                arguments[name] = defaults[name]
                to_set.remove(name)
            elif name in can_calc:
                to_set.remove(name)

    # Cluster packages is particularly magic
    # as it depends on the config filename which depends on the initial set
    # of arguments.
    to_set.remove('cluster_packages')

    # Prompt user to provide all unset arguments. If a config file was specified
    # output
    user_arguments = prompt_arguments(options.non_interactive, to_set, defaults, can_calc)
    arguments = update_dictionary(arguments, user_arguments)

    if options.save_user_config:
        # TODO(cmaloney): Add a test user config can be looped around
        # NOTE: We write arguments here, not the user_arguments which wer prompted for just now
        # because we want to include all input arguments. After this point there are calculated /
        # default arguments set.
        write_json(options.save_user_config, arguments)
        print("User Config saved to:", options.save_user_config)

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
    arguments['config_id'] = config_id

    # Calculate the set of cluster package ids, put them into 'cluster_packages'
    # This isn't included in the 'final arguments', but it is computable from it
    # so this isn't a "new" argument, just a "derived" argument.
    def get_package_id(package_name):
        pkg_id_str = "{}--setup_{}".format(package_name, config_id)
        # validate the pkg_id_str generated is a valid PackageId
        PackageId(pkg_id_str)
        return pkg_id_str

    cluster_package_ids = []

    # Calculate all the cluster package IDs.
    for package_name in cluster_packages:
        cluster_package_ids.append(get_package_id(package_name))

    # NOTE: Not pretty-printed to make it easier to drop into YAML as a one-liner
    arguments['cluster_packages'] = json.dumps(cluster_package_ids)

    # Save config parameters
    if options.save_final_config:
        write_json(options.save_final_config, arguments)
        print("Fully expanded configuration saved to:", options.save_final_config)

    # Fill in the template parameters
    rendered_templates = render_templates(templates, arguments)

    cluster_package_info = {}

    # Render all the cluster packages
    for package_name in cluster_packages:
        package_id = get_package_id(package_name)
        package_filename = 'packages/{}/{}.tar.xz'.format(
            package_name,
            package_id)

        # Build the package
        do_gen_package(rendered_templates[package_name], package_filename)

        cluster_package_info[package_name] = {
            'id': package_id,
            'filename': package_filename
        }

    # Add in the add_services util. Done here instead of the initial
    # map since we need to bind in parameters
    def add_services(cloudconfig):
        return add_units(cloudconfig, rendered_templates['dcos-services'])

    utils.add_services = add_services

    return Bunch({
        'arguments': arguments,
        'cluster_packages': cluster_package_info,
        'templates': rendered_templates,
        'utils': utils
    })


def generate(
        # CLI options
        options,
        # Which template directories to include
        mixins,
        # Arbitrary jinja template to parse
        extra_templates=dict(),
        # config.json parameters
        arguments=dict(),
        # Additional YAML to load and merge into pkgpanda
        extra_cluster_packages=[]):
    try:
        # Set the logging level
        if options.log_level == "debug":
          log.basicConfig(level=log.DEBUG)
          log.debug("Log level set to DEBUG")
        elif options.log_level == "info":
          log.basicConfig(level=log.INFO)
          log.info("Log level set to INFO")
        else:
          log.error("Logging option not available: %s", options.log_level)
          sys.exit(1)

        log.info("Generating configuration files from user input:")
        return do_generate(options, mixins, extra_templates, arguments, extra_cluster_packages)
    except jinja2.TemplateSyntaxError as ex:
        print("ERROR: Jinja2 TemplateSyntaxError")
        print("{}:{} - {}".format(
            ex.filename if ex.filename else (ex.name if ex.name else '<>'),
            ex.lineno,
            ex.message))
        sys.exit(1)
