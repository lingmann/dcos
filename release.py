#!/usr/bin/env python3
"""
Creates docker image run environment for installer and
packages it into a bash script
"""
import argparse
import os
import subprocess

DCOS_INSTALLER_COMMIT = os.getenv("DCOS_INSTALLER_COMMIT", None)
DCOS_IMAGE_COMMIT = os.getenv("DCOS_IMAGE_COMMIT", None)
CHANNEL_NAME = os.getenv("CHANNEL_NAME", 'testing')
BOOTSTRAP_ID = os.getenv("BOOTSTRAP_ID", 'deadbeef')

def get_git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().replace("\n","")
    except:
        print("Unable to parse git revision! Git must be installed.")
        exit(1)

def write_string(filename, data):
    with open(filename, "w+") as f:
        return f.write(data)

def load_string(filename):
    with open(filename) as f:
        return f.read().strip()

def do_create():
    print("Creating web-installer with the following environment:")
    print("DCOS_INSTALLER_COMMIT = {}".format(DCOS_INSTALLER_COMMIT))
    print("DCOS_IMAGE_COMMIT = {}".format(DCOS_IMAGE_COMMIT))
    print("CHANNEL_NAME = {}".format(CHANNEL_NAME))
    print("BOOTSTRAP_ID= {}".format(BOOTSTRAP_ID))
    # make docker
    docker_image_name = "dcos_installer:{}".format(DCOS_INSTALLER_COMMIT)
    # Write Dockerfile
    dockerfile_contents = load_string('Dockerfile.in').format(
            DCOS_IMAGE_COMMIT=DCOS_IMAGE_COMMIT,
            CHANNEL_NAME=CHANNEL_NAME,
            BOOTSTRAP_ID=BOOTSTRAP_ID)
    write_string('Dockerfile', dockerfile_contents)
    # Build Docker image
    subprocess.check_call(['docker', 'build', '-t', docker_image_name, "."])
    # Export docker image
    installer_tar = "dcos_installer_{}.tar".format(DCOS_INSTALLER_COMMIT)
    subprocess.check_call(
        ['docker', 'save', docker_image_name],
        stdout=open(installer_tar, 'w'))
    # Write script to file
    installer_filename = "dcos_installer.sh"
    write_string(
        installer_filename,
        load_string('dcos_installer.sh.in').format(installer_tar=installer_tar, docker_image_name=docker_image_name) + '\n#EOF#\n')
    # Attach docker image to script
    subprocess.check_call(['tar', 'cvf', '-', installer_tar], stdout=open(installer_filename, 'a'))
    # Make script executbale
    subprocess.check_call(['chmod', '+x', installer_filename])

def parse_args():
    parser = argparse.ArgumentParser(description="Creates installer as dcos_installer.sh")
    parser.add_argument("--create", action="store_true", help="Create the installer script")
    parser.add_argument("--version", action="store_true", help="Print the git SHA of this revision")
    return parser.parse_args()

def main(args):
    if args.create:
        do_create()
    elif args.version:
        print(DCOS_INSTALLER_COMMIT)
    else:
        exit(0)

if __name__=='__main__':
    arguments = parse_args()
    main(arguments)
