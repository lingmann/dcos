import logging
import os
import subprocess
import sys

import gen
import pkgpanda
import providers.bash as bash
from dcos_installer.util import IP_DETECT_PATH, SERVE_DIR

log = logging.getLogger(__name__)


def do_configure(real_config):
    gen_options = gen.get_options_object()
    gen_options.output_dir = SERVE_DIR
    gen_options.assume_defaults = True
    gen_options.non_interactive = True
    subprocess.check_output(['mkdir', '-p', SERVE_DIR])

    gen_out = do_onprem(
        gen_options,
        bash,
        ['bash', 'centos', 'onprem'],
        real_config)

    # Get bootstrap from artifacts
    fetch_bootstrap(gen_out.arguments['bootstrap_id'])
    # Write some package metadata
    pkgpanda.write_json('/genconf/cluster_packages.json', gen_out.cluster_packages)


def do_onprem(gen_options, provider_module, mixins, genconf_config):
    if 'BOOTSTRAP_ID' in os.environ:
        bootstrap_id = os.environ['BOOTSTRAP_ID']
    else:
        log.error("BOOTSTRAP_ID must be set in environment to run.")
        return

    arguments = {
        'ip_detect_filename': IP_DETECT_PATH,
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
        options=gen_options,
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
    if not os.path.exists(local_cache_filename):
        log.error("""
genconf/serve/bootstrap/{} not found, please make sure the correct BOOTSTRAP_ID is set in the environment.
""".format(bootstrap_filename))
        raise

    log.info("Copying bootstrap out of cache")
    try:
        subprocess.check_output(['mkdir', '-p', '/genconf/serve/bootstrap/'])
        subprocess.check_output(['cp', local_cache_filename, save_path])
    except (KeyboardInterrupt, subprocess.CalledProcessError) as ex:
        log.error("Copy failed or interrupted %s", ex.cmd)
        log.error("Failed commandoutput: %s", ex.output)
        cleanup_and_exit()
