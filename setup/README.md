# Generates setup / config files for DCOS

Generates the files which need to be put on individual hosts in order to install DCOS on a cobmination of "Hardware Provider" and "Distribution".

## Planned extensions:

Encoding site-specific details (Gen me customer X's setup)
  - don't mask etcd
  - multiple slave groups
  - enable certain modules

# Supported Platforms

1. Hardware Providers (Platform, Distribution Method):
  - AWS, GCE, Azure, Puppet, Chef, Ansible, Salt, Vagrant, DCOS, Docker, Standalone (Unpack this tar onto the root fs)
2. Distribution:
  - CoreOS, CentOS, RHEL, Debian, Ubuntu

Platforms (provider + distribution) in active use / support are whitelisted.


# Design

Provider specifies required parameters for DCOS components (These can be specified as variables for the provider). These parameters are fed into a function which then returns the config files + services which need to be put on the hosts. It also specifies the additional files needed to make a machine have each of the different pre-defined DCOS roles.

The information provided by DCOS then gets distribution, provider, and provider+distro specific configuration files added. For example, on cloud providers + CoreOS we disable etcd.

The information then can be converted by provider-specific code into alternate formats as needed (Make a cloud-config or generate Salt config files).
