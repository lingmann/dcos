#!/usr/bin/env python3
"""Generates DCOS packages and configuration."""
import os
import subprocess
import sys
from subprocess import CalledProcessError

import gen
import gen.calc
import providers.bash as bash
from dcos_installer.log import DCOSLog

log = DCOSLog(__name__).log


def now(options):
    """
    Entrypoint to configuration generation with the DCOS-image gen library.
    """
    # Map the options from web installer to the gen options object
    gen_opts = gen.get_options_object()
    gen_opts.log_level = options.log_level
    gen_opts.config = options.config_path
    gen_opts.output_dir = options.serve_directory
    gen_opts.assume_defaults = False
    gen_opts.non_interactive = True

    # Generate on-prem/bash configuration
    gen_out = do_gen(options, gen_opts, bash, ['bash', 'centos', 'onprem'])

    # Fetch the bootstrap tarball for our configuration
    fetch_bootstrap(gen_out.arguments['channel_name'], gen_out.arguments['bootstrap_id'])


def do_gen(options, gen_opts, provider_module, mixins):
    """
    Does on prem specific configuration generation.
    """
    # We set the channel_name, bootstrap_id in env as to not expose it to users but still make it switchable
    if 'CHANNEL_NAME' in os.environ:
        channel_name = os.environ['CHANNEL_NAME']
    else:
        log.error("CHANNEL_NAME must be set in environment to run.")
        sys.exit(1)

    if 'BOOTSTRAP_ID' in os.environ:
        bootstrap_id = os.environ['BOOTSTRAP_ID']
    else:
        log.error("BOOTSTRAP_ID must be set in environment to run.")
        sys.exit(1)

    gen_out = gen.generate(
        arguments={
            'ip_detect_filename': options.ip_detect_path,
            'channel_name': channel_name,
            'bootstrap_id': bootstrap_id
        },
        options=gen_opts,
        mixins=mixins,
        extra_cluster_packages=['onprem-config']
        )
    provider_module.generate(gen_out, options.output_dir)
    return gen_out


def fetch_bootstrap(channel_name, bootstrap_id):
    """
    Fetch the bootstrap tarball for a given provider and configuration.
    """
    bootstrap_filename = "{}.bootstrap.tar.xz".format(bootstrap_id)
    dl_url = "https://downloads.mesosphere.com/dcos/{}/bootstrap/{}".format(
        channel_name,
        bootstrap_filename)
    save_path = "/genconf/serve/bootstrap/{}".format(bootstrap_filename)

    def cleanup_and_exit():
        """
        Cleanly exit if shit breaks.
        """
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except OSError as ex:
                log.error(ex.strerror)
        sys.exit(1)

    if not os.path.exists(save_path):
        # Check if there is an in-container copy of the bootstrap tarball, and
        # if so copy it across
        local_cache_filename = "/artifacts/" + bootstrap_filename
        if os.path.exists(local_cache_filename):
            log.info("Copying bootstrap out of cache")
            try:
                subprocess.check_call(['mkdir', '-p', '/genconf/serve/bootstrap/'])
                subprocess.check_call(['cp', local_cache_filename, save_path])
                return
            except (KeyboardInterrupt, CalledProcessError) as ex:
                log.error("Copy failed or interrupted %s", ex.cmd)
                cleanup_and_exit()

        log.info("Downloading bootstrap tarball from %s", dl_url)
        curl_out = ""
        try:
            subprocess.check_call(['mkdir', '-p', '/genconf/serve/bootstrap/'])
            curl_out = subprocess.check_output([
                "/usr/bin/curl", "-fsSL", "-o", save_path, dl_url])
        except (KeyboardInterrupt, CalledProcessError) as ex:
            log.error("Download failed or interrupted %s", curl_out)
            cleanup_and_exit()
