import logging
import os
import subprocess
import sys

import gen
import pkgpanda
import providers.bash as bash
import yaml
from dcos_installer.util import IP_DETECT_PATH, SERVE_DIR

mock_config = yaml.load("""
---
# Cluster configuration for DCOS
# This is the local path on the target machine where the installer dumps the
# packages and bootstrap tar ball.
bootstrap_url: 'file:///opt/dcos_install_tmp'

# The name of the cluster, we default to the following:
cluster_name: 'Mesosphere: The Data Center Operating System'

# Docker GC defaults, recommended to leave as default unless you're advanced.
docker_remove_delay: '1hrs'

# The default backend for Exhibitor is Zookeeper. Advanced options are
# shared_fs and aws_s3
exhibitor_storage_backend: zookeeper

# If you use the default Zk backend for Exhibitor, you need to pass in
# the IPs of the Zk cluster for it to use. This is a COMMA SEPARATED LIST,
# not to be confused with an actual array. You must also pass the :$PORT.
exhibitor_zk_hosts: 10.33.2.20:2181

# This is an arbitrary path for Exhibitor to dump its zk config to.
exhibitor_zk_path: /home/vagrant

# More garbage collection, don't change unless you're advanced.
gc_delay: '2days'

# We default master discovery to a static list of masters. Advanced options
# are 'keepalived' and 'cloud_dynamic'
master_discovery: static

# Since we're defaulting to master list, we pass that static list of masters.
# Recommended deployment as at least 3 masters and a maximum of 5. It's not
# Recommended that you deploy even number of masters.
master_list: '["10.33.2.21"]'

# This is the list of upstream DNS resolvers that Mesos DNS will use.
resolvers: '["8.8.8.8", "8.8.4.4"]'

# Default roles, do not change unless you're advanced.
roles: slave_public

# Default weights, do not change unless you're advanced.
weights: slave_public=1
""")

log = logging.getLogger(__name__)


def do_configure():
    # TODO(malnick) we're setting bootstrap to our foo bootstrap
    # for demo purposes only
    os.environ['BOOTSTRAP_ID'] = 'e2ade83b3197150980714635c6752bc9ece1e0ca'
#    os.environ['CHANNEL_NAME'] = 'testing/continuous'

    gen_options = gen.get_options_object()
    gen_options.output_dir = SERVE_DIR
    gen_options.assume_defaults = True
    gen_options.non_interactive = True
    subprocess.check_output(['mkdir', '-p', SERVE_DIR])

    gen_out = do_onprem(
        gen_options,
        bash,
        ['bash', 'centos', 'onprem'],
        mock_config)

    # Get bootstrap from artifacts
    fetch_bootstrap(gen_out.arguments['bootstrap_id'])
    # Write some package metadata
    pkgpanda.write_json('/genconf/cluster_packages.json', gen_out.cluster_packages)


def do_onprem(gen_options, provider_module, mixins, genconf_config):
    # if 'CHANNEL_NAME' in os.environ:
    #    channel_name = os.environ['CHANNEL_NAME']
    # else:
    #    log.error("CHANNEL_NAME must be set in environment to run.")
    #    return

    if 'BOOTSTRAP_ID' in os.environ:
        bootstrap_id = os.environ['BOOTSTRAP_ID']
    else:
        log.error("BOOTSTRAP_ID must be set in environment to run.")
        return

    arguments = {
        'ip_detect_filename': IP_DETECT_PATH,
        # 'channel_name': channel_name,
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
    assert os.path.exists(local_cache_filename)
    log.info("Copying bootstrap out of cache")
    try:
        subprocess.check_output(['mkdir', '-p', '/genconf/serve/bootstrap/'])
        subprocess.check_output(['cp', local_cache_filename, save_path])
    except (KeyboardInterrupt, CalledProcessError) as ex:
        log.error("Copy failed or interrupted %s", ex.cmd)
        log.error("Failed commandoutput: %s", ex.output)
        cleanup_and_exit()
