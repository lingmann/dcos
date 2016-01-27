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

import importlib
import inspect
import json
import logging as log
import os
import os.path
import sys
from copy import copy, deepcopy
from itertools import chain
from subprocess import check_call
from tempfile import TemporaryDirectory

import yaml
from pkg_resources import resource_string
from pkgpanda import PackageId
from pkgpanda.util import make_tar

import gen.template

# List of all roles all templates should have.
role_names = {"master", "slave", "slave_public"}

role_template = '/etc/mesosphere/roles/{}'

CLOUDCONFIG_KEYS = {'coreos', 'runcmd', 'apt_sources', 'root'}
PACKAGE_KEYS = {'package', 'root'}


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

            # Merge sets
            if isinstance(v, set) and isinstance(base_copy[k], set):
                base_copy[k] |= v
                continue

            # Unknwon types
            raise ValueError("Can't merge type {} into type {}".format(type(v), type(base_copy[k])))
        except ValueError as ex:
            raise ValueError("{} inside key {}".format(ex, k)) from ex
    return base_copy


# Order in a file determines order in which things like services get placed,
# changing it can break components (Ex: moving dcos-download and dcos-setup
# too early will break some configurations).
def get_name(mixin_name, target, sep='/'):
    if mixin_name:
        return mixin_name + sep + target
    else:
        return target


# Render the Jinja/YAML into YAML, then load the YAML and merge it to make the
# final configuration files.
def render_templates(template_names, arguments):
    rendered_templates = dict()
    for name, templates in template_names.items():
        full_template = None
        for template in templates:

            # Render the template. If the file doesn't exist that just means the
            # current mixin doesn't have it, which is fine.
            try:
                rendered_template = gen.template.parse_resources(template).render(arguments)
            except FileNotFoundError:
                continue

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
    parameters = {'variables': set(), 'sub_scopes': dict()}
    for template_list in template_dict.values():
        assert isinstance(template_list, list)
        for template in template_list:
            assert isinstance(template, str)
            try:
                ast = gen.template.parse_resources(template)
                scoped_arguments = ast.get_scoped_arguments()
                parameters = merge_dictionaries(parameters, scoped_arguments)
            except FileNotFoundError as ex:
                # Needs to be implemented with a logger
                log.debug("Template not found: %s", ex)

    return parameters


def update_dictionary(base, addition):
    base_copy = base.copy()
    base_copy.update(addition)
    return base_copy


def get_function_parameters(function):
    return set(inspect.signature(function).parameters)


# Depth first search argument calculator. Detects cycles, as well as unmet
# dependencies.
# TODO(cmaloney): Separate chain / path building when unwinding from the root
#                 error messages.
class DFSArgumentCalculator():
    def __init__(self, setters):
        self._setters = setters
        self._arguments = dict()
        self.__in_progress = set()

    def _calculate_argument(self, name):
        # Filter out any setters which have predicates / conditions which are
        # satisfiably false.
        def all_conditions_met(setter):
            for condition_name, condition_value in setter.conditions:
                try:
                    if self[condition_name] != condition_value:
                        return False
                except AssertionError as ex:
                    raise AssertionError(
                        str(ex) +
                        " trying to test condition {}={}".format(condition_name, condition_value))
            return True

        # Find the right setter to calculate the argument.
        feasible = list(filter(all_conditions_met, self._setters.get(name, list())))

        if len(feasible) == 0:
            raise AssertionError("No known way to set {}".format(name))

        # Filtier out all optional setters if there is more than one way to set.
        if len(feasible) > 1:
            feasible = list(filter(lambda setter: not setter.is_optional, feasible))

        assert len(feasible) > 0, "Had multiple optionals. Template internal error."

        # Must be calculated but user tried to provide.
        if len(feasible) == 2 and (feasible[0].is_user or feasible[1].is_user):
            raise AssertionError(
                "{} must be calculated but was explicitly set in config. Remove it from the config.".format(name))

        if len(feasible) > 1:
            # TODO(cmaloney): Include the different calc functions / conditions.
            raise AssertionError("Internal error, Multiple ways to set {}.".format())

        setter = feasible[0]

        # Get values for the parameters, then call. the setter function.
        kwargs = {}
        for parameter in setter.parameters:
            kwargs[parameter] = self[parameter]

        return setter.calc(**kwargs)

    def __getitem__(self, name):
        if name in self._arguments:
            if self._arguments[name] is None:
                raise AssertionError("{} cannot be calculated. See previous error.".format(name))
            return self._arguments[name]

        # Detect cycles by checking if we're in the middle of calculating the
        # argument being asked for
        if name in self.__in_progress:
            raise AssertionError("Internal error, cycle detected. re-encountered {}".format(name))

        self.__in_progress.add(name)
        try:
            self._arguments[name] = self._calculate_argument(name)
            return self._arguments[name]
        except AssertionError as ex:
            self._arguments[name] = None
            raise AssertionError(str(ex) + " while calculating {}".format(name)) from ex
        except:
            self._arguments[name] = None
            raise
        finally:
            self.__in_progress.remove(name)

    def calculate(self, scope):
        # TODO(cmaloney): Collect exceptions and return as structured results.
        # Force calculation of all arguments by accessing the arguments in this
        # scope and recursively all sub-scopes.
        for name in scope.get('variables', set()):
            self[name]

        for name, sub_scope in scope.get('sub_scopes', 'dict').items():
            choice = self[name]
            if choice not in sub_scope:
                raise AssertionError("Illegal choice. {} for {}".format(choice, name))
            self.calculate(sub_scope[choice])

        return self._arguments


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
    parser.add_argument('--assume-defaults', action='store_true')
    parser.add_argument('--non-interactive', action='store_true')
    parser.add_argument(
        '-l',
        '--log-level',
        default='info',
        choices=['debug', 'info'],
        help='Logging level. Default: info. Options: info, debug.')

    return parser


def do_gen_package(config, package_filename):
    # Generate the specific dcos-config package.
    # Version will be setup-{sha1 of contents}
    # Forcibly set umask so that os.makedirs() always makes directories with
    # uniform permissions
    os.umask(0o000)

    with TemporaryDirectory("gen_tmp_pkg") as tmpdir:

        # Only contains package, root
        assert config.keys() == {"package"}

        # Write out the individual files
        for file_info in config["package"]:
            if file_info['path'].startswith('/'):
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

    log.info("Package filename: %s", package_filename)


def prompt_argument(non_interactive, name, can_calc=False, default=None, possible_values=None):
    if non_interactive:
        log.error("Unset variable in configuration: %s", name)
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

        descriptions = json.loads(resource_string(__name__, "descriptions.json"))

        if name in descriptions:
            print("")
            print("Please provide values for: %s" % name)
            print(descriptions[name])

        value = input('{}{}{}: '.format(name, default_str, possible_values_str))

        # Make sure value is one of the allowed values
        if possible_values is not None and value not in possible_values:
            log.error("Value not one of the possible values: %s", ','.join(possible_values))
            continue

        if value:
            return value
        if default:
            return default
        if can_calc:
            return None

        log.error("ERROR: Must provide a value")


def prompt_arguments(can_set, defaults, can_calc):
    arguments = dict()
    for name in sorted(can_set):
        result = prompt_argument(False, name, name in can_calc, defaults.get(name))

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


def get_mixin_functions(name):
    modulename = 'gen.' + get_name(name, 'calc', sep='.')
    try:
        return importlib.import_module(modulename).entry
    except ImportError as ex:
        # TODO(cmaloney): Make the module not existing a hard error.
        log.debug("Module not found: %s", ex)
        return {}


def validate_arguments_strings(arguments):
    has_error = False
    # Validate that all keys and vlaues of arguments are strings
    for k, v in arguments.items():
        if not isinstance(k, str):
            print("ERROR: all keys in arguments must be strings. '{}' isn't.".format(k))
            has_error = True
        if not isinstance(v, str):
            print("ERROR: all values in arguments must be strings. Value for argument ", k,
                  " isn't. Given value: {}".format(v))
            has_error = True

    if has_error:
        sys.exit(1)


def extract_files_with_path(start_files, paths):
    found_files = []
    found_file_paths = []
    left_files = []

    for file_info in deepcopy(start_files):
        if file_info['path'] in paths:
            found_file_paths.append(file_info['path'])
            found_files.append(file_info)
        else:
            left_files.append(file_info)

    # Assert all files were found. If not it was a programmer error of some form.
    assert set(found_file_paths) == set(paths)
    # All files still belong somewhere
    assert len(found_files) + len(left_files) == len(start_files)

    return found_files, left_files


def validate_given(validate_fns, arguments):
    fns_by_arg = dict()

    for fn in validate_fns:
        parameters = get_function_parameters(fn)
        assert len(parameters) == 1, "Validate functions must take exactly one parameter currently."
        # Get out the one and only parameter's name. This will break really badly
        # if functions have more than one parameter (We'll call for
        # each parameter with only one parameter)
        for parameter in parameters:
            fns_by_arg[parameter] = fn

    errors = {}

    def noop(_):
        return

    for name, value in arguments.items():
        try:
            fns_by_arg.get(name, noop)(value)
        except AssertionError as ex:
            errors[name] = ex.args[0]

    return errors


class Setter():
    # NOTE: value may either be a function or a string.
    def __init__(self, name, value, is_optional, conditions, is_user):
        assert isinstance(conditions, list)
        self.name = name
        self.is_optional = is_optional
        self.conditions = conditions
        self.is_user = is_user

        def get_value():
            return value

        if isinstance(value, str):
            self.calc = get_value
            self.parameters = set()
        else:
            assert callable(value), "{} should be a string or callable. Got: {}".format(name, value)
            self.calc = value
            self.parameters = get_function_parameters(value)

    def __repr__(self):
        return "<Setter {}{}{}, conditions: {}{}>".format(
            self.name,
            ", optional" if self.is_optional else "",
            ", user" if self.is_user else "",
            self.conditions,
            ", parameters {}".format(self.parameters))


# Validate all arguments passed in actually correspond to parameters to
# prevent human typo errors.
# This includes all possible sub scopes (Including config for things you don't use is fine).
def flatten_parameters(scoped_parameters):
    flat = copy(scoped_parameters.get('variables', set()))
    for name, possible_values in scoped_parameters.get('sub_scopes', dict()).items():
        flat.add(name)
        for sub_scope in possible_values.values():
            flat |= flatten_parameters(sub_scope)

    return flat


def do_generate(
        mixins,
        extra_templates,
        user_arguments,
        cc_package_files):

    # TODO(cmaloney): Remove flattening and teach lower code to operate on list
    # of mixins.
    templates = dict()
    setters = dict()
    validate = list()

    # Make sure all user provided arguments are strings.
    validate_arguments_strings(user_arguments)

    # Empty string (top level directory) is always implicitly included
    assert '' not in mixins
    assert None not in mixins

    package_names = list(sorted(set(
        ['dcos-config', 'dcos-detect-ip', 'dcos-metadata'])))
    core_templates = ['cloud-config', 'dcos-services']

    # Add the empty mixin so we pick up top-level config.
    mixins.append('')

    # Make sure no mixins were given twice
    assert len(set(mixins)) == len(mixins), "Repeated mixin in list of mixins: {}".format(mixins)

    def add_setter(name, value, is_optional, conditions, is_user):
        setters.setdefault(name, list()).append(Setter(name, value, is_optional, conditions, is_user))

    # Add in all user arguments as setters
    for name, value in user_arguments.items():
        add_setter(name, value, False, [], True)

    for mixin in mixins:
        mixin_templates = get_templates(mixin, package_names, core_templates)
        templates = merge_dictionaries(templates, mixin_templates)

        # TODO(cmaloney): merge_dictionaries, hard error on duplicate leaf keys.
        # Right now we arbitrarily get one of them in conflicts.

        def add_conditional_scope(scope, conditions):
            nonlocal validate

            # TODO(cmaloney): 'defaults' are the same as 'can' and 'must' is identical to 'arguments' except
            # that one takes functions and one takes strings. Simplify to just 'can', 'must'.
            assert scope.keys() <= {'validate', 'can', 'defaults', 'must', 'arguments', 'conditional'}

            validate += scope.get('validate', list())

            for name, fn in chain(scope.get('must', dict()).items(), scope.get('arguments', dict()).items()):
                add_setter(name, fn, False, conditions, False)

            for name, fn in chain(scope.get('can', dict()).items(), scope.get('defaults', dict()).items()):
                add_setter(name, fn, True, conditions, False)

            for name, cond_options in scope.get('conditional', dict()).items():
                for value, sub_scope in cond_options.items():
                    add_conditional_scope(sub_scope, conditions + [(name, value)])

        add_conditional_scope(get_mixin_functions(mixin), [])

    # Make sure only yaml templates have more than one mixin providing them / are provided more than once.
    for name, template_list in templates.items():
        if len(template_list) > 1:
            for template in template_list:
                if not template.endswith('.yaml'):
                    log.error(
                        "Only know how to merge YAML templates at this point in time. Can't" +
                        " merge template %s in template_list %s", name, template_list)
                    sys.exit(1)

    # Inject extra_templates and parameters inside.
    templates.update(extra_templates)
    mandatory_parameters = get_parameters(templates)

    all_parameters = flatten_parameters(mandatory_parameters)
    for setter_list in setters.values():
        for setter in setter_list:
            all_parameters |= setter.parameters

    for argument in user_arguments:
        if argument not in all_parameters:
            log.error("ERROR: Argument '%s' given but not in possible parameters: %s",
                      argument,
                      ', '.join(all_parameters))
            sys.exit(1)

    def add_builtin(name, value):
        add_setter(name, value, False, [], False)

    add_builtin('mixins', json.dumps(mixins, **json_prettyprint_args))
    add_builtin('package_names', json.dumps(list(package_names), **json_prettyprint_args))
    add_builtin('user_arguments', json.dumps(user_arguments, **json_prettyprint_args))

    # Calculate the remaining arguments.
    arguments = DFSArgumentCalculator(setters).calculate(mandatory_parameters)

    # Validate arguments.
    validate_arguments_strings(arguments)
    errors = validate_given(validate, arguments)
    if errors:
        for key, msg in errors.items():
            log.error("ERROR: Argument '%s' with value '%s' didn't pass validation: %s", key, arguments[key], msg)
        sys.exit(1)

    log.info("Final arguments:" + json.dumps(arguments, **json_prettyprint_args))

    # Fill in the template parameters
    rendered_templates = render_templates(templates, arguments)

    # Validate there aren't any unexpected top level directives in any of the files
    # (likely indicates a misspelling)
    for name, template in rendered_templates.items():
        if name == 'dcos-services':  # yaml list of the service files
            assert isinstance(template, list)
        elif name == 'cloud-config':
            assert template.keys() <= CLOUDCONFIG_KEYS, template.keys()
        elif isinstance(template, str):  # Not a yaml template
            pass
        else:  # yaml template file
            log.debug("validating template file %s", name)
            assert template.keys() <= PACKAGE_KEYS, template.keys()

    # Extract cc_package_files out of the dcos-config template and put them into
    # the cloud-config package.
    cc_package_files, dcos_config_files = extract_files_with_path(rendered_templates['dcos-config']['package'],
                                                                  cc_package_files)
    rendered_templates['dcos-config'] = {'package': dcos_config_files}

    # Add a empty pkginfo.json to the cc_package_files.
    # Also assert there isn't one already (can only write out a file once).
    for item in cc_package_files:
        assert item['path'] != '/pkginfo.json'

    # If there aren't any files for a cloud-config package don't make one start
    # existing adding a pkginfo.json
    if len(cc_package_files) > 0:
        cc_package_files.append({
            "path": "/pkginfo.json",
            "content": "{}"})

    for item in cc_package_files:
        assert item['path'].startswith('/')
        item['path'] = '/etc/mesosphere/setup-packages/dcos-provider-{}--setup'.format(
            arguments['provider']) + item['path']
        rendered_templates['cloud-config']['root'].append(item)

    cluster_package_info = {}

    # Render all the cluster packages
    for package_id_str in json.loads(arguments['cluster_packages']):
        package_id = PackageId(package_id_str)
        package_filename = 'packages/{}/{}.tar.xz'.format(
            package_id.name,
            package_id_str)

        # Build the package
        do_gen_package(rendered_templates[package_id.name], package_filename)

        cluster_package_info[package_id.name] = {
            'id': package_id_str,
            'filename': package_filename
        }

    # Convert cloud-config to just contain write_files rather than root
    cc = rendered_templates['cloud-config']

    # Shouldn't contain any packages. Providers should pull what they need to
    # late bind out of other packages via cc_package_file.
    assert 'package' not in cc
    cc_root = cc.pop('root', [])
    # Make sure write_files exists.
    assert 'write_files' not in cc
    cc['write_files'] = []
    # Do the transform
    for item in cc_root:
        assert item['path'].startswith('/')
        cc['write_files'].append(item)
    rendered_templates['cloud-config'] = cc

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
        # Which template directories to include
        mixins,
        # Arbitrary jinja template to parse
        extra_templates=dict(),
        # config.json parameters
        arguments=dict(),
        cc_package_files=[]):

    log.info("Generating configuration files...")
    return do_generate(mixins, extra_templates, arguments, cc_package_files)
