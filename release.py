#!/usr/bin/env python3
"""
Create DCOS installer executable

Usage:
  release ( create | test )

Options:
  -h --help    Show this screen
  --version    Show version
"""
import argparse
import subprocess

from docopt import docopt

try:
    GIT_SHA = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().replace("\n","")
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
    # make docker
    docker_image_name = "dcos_installer:{}".format(GIT_SHA)
    subprocess.check_call(['docker', 'build', '-t', docker_image_name, "."])
    installer_filename = "dcos_installer.sh"
    installer_tar = "docker_installer_{}.tar".format(GIT_SHA)
    # Export docker image
    subprocess.check_call(
        ['docker', 'save', docker_image_name],
        stdout=open(installer_tar, 'w'))
    # Write script to file
    write_string(
        installer_filename,
        load_string('dcos_installer.sh.in').format(installer_tar=installer_tar, docker_image_name=docker_image_name) + '\n#EOF#\n')
    # Attach docker image to script
    subprocess.check_call(['tar', 'cvf', '-', installer_tar], stdout=open(installer_filename, 'a'))
    # Make script executbale
    subprocess.check_call(['chmod', '+x', installer_filename])

def do_test():
    pass

def main(arguments):
    if arguments["create"] is True:
        do_create()
    elif arguments["test"] is True:
        do_test()

if __name__=='__main__':
    arguments = docopt(__doc__, version=GIT_SHA)
    main(arguments)
