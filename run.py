#!/usr/bin/env python3
# ENV['channelname'] && ['bootstrap_id'] need to be set here.

import os
import sys
import argparse

from dcos_installer import DcosInstaller

# Get the current relative directory
project_path=os.path.dirname(os.path.realpath(__file__))

def parse_args(args):
    """
    Parse CLI arguments and return a map of options.
    """
    # Get the user's homedir in a cross platfrom manner
    # Can set top level install dir as env var or accept default in $HOME
    homedir    = os.path.expanduser('~')
    if 'DCOS_INSTALL_DIR' in os.environ:
        installdir = os.environ['DCOS_INSTALL_DIR']
    else:
        installdir = '{}/dcos-installer'.format(homedir)
        
    parser = argparse.ArgumentParser(description='Install DCOS on-premise')
    parser.add_argument(
        '--log-directory',
        type=str,
        default='{}/logs'.format(installdir),
        help='Path to the logging directory. Used for preflight.log and deploy.log..')
    
    parser.add_argument(
        '--dcos-install-script-path',
        type=str,
        default='{}/dcos_installer/templates/install_dcos.sh'.format(project_path),
        help='The path to install_dcos.sh script. Defaults to sibling of the project repo.')

    parser.add_argument(
        '--ssh-key-path',
        type=str,
        default='{}/ssh_key'.format(installdir),
        help='The path to the private ssh key for preflight and deploy functionality.')

    parser.add_argument(
        '--hosts-yaml-path',
        type=str,
        default='{}/hosts.yaml'.format(installdir),
        help='The path to the hosts.yaml for preflight and deploy functionlity.')

    parser.add_argument(
        '--ssh-user-path',
        type=str,
        default='{}/ssh_user'.format(installdir),
        help='The path to ssh_user file containing the name of the user for SSH access. Required for preflight and deploy functionality.')

    parser.add_argument(
        '--ip-detect-path',
        type=str,
        default='{}/ip-detect'.format(installdir),
        help='The path to the ip-detect script.')

    parser.add_argument(
        '-c',
        '--config-path',
        type=str,
        default='{}/dcos_config.yaml'.format(installdir),
        help='The path to dcos_config.yaml.')

    # TODO - implement CLI utility
    parser.add_argument(
        '-d',
        '--deploy',
        action='store_true',
        default=False,
        help='Execute a deploy. Assumes preflight checks have already been executed and the cluster is in a usable state.')

    parser.add_argument(
        '-i',
        '--install-directory',
        type=str,
        default=installdir,
        help='The install directory for the DCOS installer.')

    parser.add_argument(
        '-l',
        '--log-level',
        type=str,
        default='info',
        choices=['info','debug'],
        help='Log level.')

    parser.add_argument(
        '-m',
        '--mode',
        type=str,
        choices=['non-interactive', 'interactive', 'web'],
        default='web',
        help='Installation mode.')

    parser.add_argument(
        '-p', 
        '--port',
        type=int,
        default=9000,
        help='Web server port number.')

    parser.add_argument(
        '--serve-directory',
        type=str,
        default='{}/serve'.format(installdir),
        help='The path to the serve directory. Used to dump generated config and packages.')

    # TODO - implement CLI utility
    parser.add_argument(
        '-pre',
        '--preflight',
        action='store_true',
        default=False,
        help='Execute the preflight checks on a series of nodes. Assumes $INSTALL_DIR/hosts.yaml exists.')

    parser.add_argument(
        '-t',
        '--test',
        action='store_true',
        default=False,
        help='Performs tests on the dcos_installer application')

    options = parser.parse_args(args)

    return options

def main():
    os.environ["CHANNEL_NAME"] = "testing/continuous"
    os.environ["BOOTSTRAP_ID"] = '0026f44d8574d508104f1e7e7a163e078e69990b'

    options=parse_args(sys.argv[1:])
    print(options)
    input()

    if options.test:
        print("Testing!")
        import subprocess
        import sys
        errno=subprocess.call('tox')
        raise SystemExit(errno)

    DcosInstaller(options)

if __name__ == '__main__':
    main()
