#!/usr/bin/env python3
import os
import sys

from dcos_installer import DcosInstaller


def main():
    channel = os.getenv("CHANNEL_NAME", None)
    bootstrap_id = os.getenv("BOOTSTRAP_ID", None)
    if channel is None:
        exit("CHANNEL_NAME must be set in environment!")
    if bootstrap_id is None:
        exit("BOOTSTRAP_ID must be set in environment!")
    DcosInstaller(sys.argv[1:])

if __name__ == '__main__':
    main()
