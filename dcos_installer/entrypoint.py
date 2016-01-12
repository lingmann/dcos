#!/usr/bin/env python3
import os
import sys

from dcos_installer import DcosInstaller


def main():
    os.getenv("CHANNEL_NAME", None)
    os.getenv("BOOTSTRAP_ID", None)
    if os.environ["CHANNEL_NAME"] is None:
        print("CHANNEL_NAME must be set in environment!")
        exit(1)
    if os.environ["BOOTSTRAP_ID"] is None:
        print("BOOTSTRAP_ID must be set in environment!")
        exit(1)
    DcosInstaller(sys.argv[1:])

if __name__ == '__main__':
    main()
