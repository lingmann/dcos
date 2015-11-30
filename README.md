# DCOS Installer

## Run locally

1. ```pip install -r requirements.txt```
2. ```./run_dcos_installer```

## Manpage

```pre
usage: run [-h] [--log-directory LOG_DIRECTORY]
           [--dcos-install-script-path DCOS_INSTALL_SCRIPT_PATH]
           [--ip-detect-path IP_DETECT_PATH] [-c CONFIG_PATH] [-d]
           [-i INSTALL_DIRECTORY] [-l {info,debug}] [-m {cli,web}] [-p PORT]
           [--serve-directory SERVE_DIRECTORY] [-pre] [-t]
```

**NAME**

`./run -- run the DCOS installer`

**SYNOPSIS**

`./run [-h | --help] [ -l | --log-level ] [ -p | --port ] [ -m | --mode ] [ -c | --config-path ] [ -d | --install-directory ]` 

**DESCRIPTION**

The DCOS installer runs a web or CLI utility to build DCOS configuration files for your cluster and exposes several deployment options.

**FLAGS**

```pre 
-c                | Configuration Path - Set the configuration path, default is $HOME/dcos/dcos-config.yaml: Accepts a valid /path/to/config.yaml.

-d                | Install Directory - Set hte configuration directory used to store and build the bootstrap tarball, defaults to $HOME/dcos: Accepts a valid /path/to/install/stuff. 

-h                | Help - Show the help menu

-l                | Log Level - Set the loglevel: 'info' or 'debug'

--log-directory   | The path to the directory to store log data from preflight and deploy modes

-m                | Mode - Set the isntaller mode, defualt is 'web': 'cli' or 'web'

-p                | Port - Override the default port of :5000. Accepts an integer.

--serve-directory | The directory to find the tarball and installer script to ship to target hosts.
```

### Configuration File 
Yaml configuration file located at `$INSTALL_DIRECTORY/dcos_config.yaml`

**EXAMPLE CONFIGURATION**

```yaml
---
# Used for configuration generation
cluster_config:
  # The URL to download the tarball - not used in deploy mode
  # Defualt: localhost
  bootstrap_url: localhost

  # The name of the DCOS cluster
  # Default: Mesosphere: The Data Center Operating System
  cluster_name: 'Mesosphere: The Data Center Operating System'

  # The installer configuration directory
  # Default: $HOME/dcos-installer/
  config_dir: /Users/malnick/dcos-installer

  # Docker garbage collection
  # Default: 1hrs
  docker_remove_delay: 1hrs

  # Zookeeper exhibitor backend
  # Default: zookeeper
  exhibitor_storage_backend: zookeeper

  # Exhibitor zookeeper hosts
  # Default: 127.0.0.1
  exhibitor_zk_hosts:
  - 127.0.0.1

  # The exhibitor storage file
  # Default: /exhibitor
  exhibitor_zk_path: /exhibitor

  # Garbage collection delay
  # Default: 2days
  gc_delay: 2days

  # The path to the ip-detect script
  # Default: $HOME/dcos-installer/ip-detect
  ip_detect_path: /Users/malnick/dcos-installer/ip-detect

  # The master discovery method
  # Default: static list (master_list)
  master_discovery: static

  # The list of target hosts that will run Mesos Masters
  # Default: []
  master_list:
  - 10.33.2.20
  - 10.0.0.2
  - 10.0.0.3

  # Deprecated value; the number of running masters
  # Calculated from master_list
  num_masters: 3

  # Upstream DNS resolvers for Mesos DNS
  # Default: TBD
  resolvers:
  - 8.8.8.8
  - 8.8.4.4

  # Default Mesos roles to install on target hosts
  # Default: slave_public
  roles: slave_public

  # Mesos weights setting
  # Default: slave_public=1
  weights: slave_public=1

# Used for SSH configuration
ssh_config:
  # The list of target hosts that will run Mesos Agents. The ip's from master_list are 
  # automagically added to this list when used via the config library in the web installer.
  # Default: []
  target_hosts:
  - 10.0.0.222
  - 10.0.0.235
  - 10.0.0.223
  - 10.0.0.224

  # The path to the private SSH key to execute remote installation on target hosts
  # Key must have root access on target hosts for installation
  # Default: $HOME/dcos-installer/ssh_key
  ssh_key_path: /Users/malnick/dcos-installer/ssh_key

  # The port to execute SSH access
  # Default: 22
  ssh_port: 22

  # The user to execute SSH and copy DCOS tarball to $HOME on taget hosts
  # Default: vagrant
  ssh_user: vagrant
```
