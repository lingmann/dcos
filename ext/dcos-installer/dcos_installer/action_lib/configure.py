import logging
import os
import subprocess
import sys

import gen
import pkgpanda
import providers.bash
from dcos_installer.util import SERVE_DIR

log = logging.getLogger(__name__)


def do_configure(gen_config):
    gen_config.update(get_gen_extra_args())

    subprocess.check_output(['mkdir', '-p', SERVE_DIR])

    validated = do_validate_gen_config(gen_config)
    if 'errors' in validated:
        errors = validated['errors']
        for optional_key in ('superuser_username', 'superuser_password_hash'):
            if optional_key in errors:
                del gen_config[optional_key]

    gen_out = gen.generate(arguments=gen_config)
    providers.bash.generate(gen_out, SERVE_DIR)

    # Get bootstrap from artifacts
    fetch_bootstrap(gen_out.arguments['bootstrap_id'])
    # Write some package metadata
    pkgpanda.write_json('/genconf/cluster_packages.json', gen_out.cluster_packages)


def get_gen_extra_args():
    if 'BOOTSTRAP_ID' in os.environ:
        bootstrap_id = os.environ['BOOTSTRAP_ID']
    else:
        log.error("BOOTSTRAP_ID must be set in environment to run.")
        raise KeyError

    arguments = {
        'cluster_id': 'TODO',
        'bootstrap_id': bootstrap_id,
        'provider': 'onprem'}
    return arguments


def do_validate_gen_config(gen_config, mixins=['bash', 'centos', 'onprem']):
    # run validate first as this is the only way we have for now to remove "optional" keys
    gen_config.update(get_gen_extra_args())
    return gen.validate(arguments=gen_config)


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
        log.warning(local_cache_filename)
        raise FileNotFoundError

    log.info("Copying bootstrap out of cache")
    try:
        subprocess.check_output(['mkdir', '-p', '/genconf/serve/bootstrap/'])
        subprocess.check_output(['cp', local_cache_filename, save_path])
    except (KeyboardInterrupt, subprocess.CalledProcessError) as ex:
        log.error("Copy failed or interrupted %s", ex.cmd)
        log.error("Failed commandoutput: %s", ex.output)
        cleanup_and_exit()
