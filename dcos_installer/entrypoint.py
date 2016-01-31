#!/usr/bin/env python3
import os
import sys

from dcos_installer import DcosInstaller


def main():
    DcosInstaller(sys.argv[1:])

if __name__ == '__main__':
    main()
