# DCOS Installer

## Run locally

1. ```pip install -r requirements.txt```
2. ```./run```

# REST API

#### / -redirects-> /api/v1
**GET**: Loads application

#### /api/v1/configure/ - TBD
**GET**: Get currently stored configuration

```json
{
  "cluster_config": {
    "exhibitor_storage_backend": "zookeeper",
    "exhibitor_zk_hosts": "127.0.0.1:2181",
    "exhibitor_zk_path": "/exhibitor",
    "master_discovery": "static",
    "num_masters": null,
    "cluster_name": "Mesosphere: The Data Center Operating System",
    "ip_detect_path": "/genconf/ip-detect",
    "bootstrap_url": "file:///opt/dcos_install_tmp",
    "resolvers": [
      "8.8.8.8",
      "8.8.4.4"
    ],
    "master_list": null,
    "docker_remove_delay": "1hrs",
    "roles": "slave_public",
    "gc_delay": "2days",
    "weights": "slave_public=1"
  },
  "ssh_config": {
    "target_hosts": [
      null
    ],
    "ssh_key_path": "/genconf/ssh_key",
    "log_directory": "/genconf/logs",
    "ssh_port": 22,
    "ssh_user": null
  }
}
```

**POST**: Save configuration. It validates configuration data, returns [config_errors.json](#_errorsjson)

```
curl -H 'Content-Type: application/json' -XPOST -d '{"ssh_config":{"ssh_user": "some_new_user"}}' localhost:5000/api/v1/configure | json
```
```json
{
  "cluster_config": {
    "exhibitor_storage_backend": "zookeeper",
    "exhibitor_zk_hosts": "127.0.0.1:2181",
    "exhibitor_zk_path": "/exhibitor",
    "master_discovery": "static",
    "num_masters": null,
    "cluster_name": "Mesosphere: The Data Center Operating System",
    "ip_detect_path": "/genconf/ip-detect",
    "bootstrap_url": "file:///opt/dcos_install_tmp",
    "resolvers": [
      "8.8.8.8",
      "8.8.4.4"
    ],
    "master_list": null,
    "docker_remove_delay": "1hrs",
    "roles": "slave_public",
    "gc_delay": "2days",
    "weights": "slave_public=1"
  },
  "ssh_config": {
    "target_hosts": [
      null
    ],
    "ssh_key_path": "/genconf/ssh_key",
    "log_directory": "/genconf/logs",
    "ssh_port": 22,
    "ssh_user": "some_new_user"
  }
}
```

#### /api/v1/preflight/
**GET**:  RETURN preflight_status.json

```
curl localhost:5000/api/v1/preflight | json
```
```json
{
  "10.0.0.3": {
    "stdout": [
      ""
    ],
    "state": "not_running",
    "returncode": -1,
    "cmd": "",
    "stderr": [
      ""
    ],
    "role": "slave"
  },
  "10.0.0.1": {
    "stdout": [
      ""
    ],
    "state": "not_running",
    "returncode": -1,
    "cmd": "",
    "stderr": [
      ""
    ],
    "role": "master"
  },
  "10.0.0.2": {
    "stdout": [
      ""
    ],
    "state": "running",
    "returncode": -1,
    "cmd": "uptime",
    "stderr": [
      ""
    ],
    "role": "slave"
  },
  "10.0.0.4": {
    "stdout": [
      ""
    ],
    "state": "success",
    "returncode": 0, 
    "cmd": "uptime",
    "stderr": [
      ""
    ],
    "stdout": [
      "13:53  up 13 days, 17:25, 3 users, load averages: 1.59 1.65 1.69",
    ]
    "role": "slave"
  },
  "10.0.0.5": {
    "stdout": [
      ""
    ],
    "state": "error",
    "returncode": 127,
    "cmd": "uptime",
    "stderr": [
      "command not found"
    ],
    "role": "slave"
  }
}
```

**POST**: Execute preflight on target hosts. Returns state.json

#### /api/v1/preflight/logs/
**GET**: Get *_preflight logs for download (this is a .tar file)

#### /api/v1/deploy/
**GET**:  RETURN state.json

**POST**: Execute install DCOS on target hosts. Return state.json.

#### /api/v1/deploy/logs/
**GET**: Get *_deploy.log data for download (this is a .tar file)

#### /api/v1/postflight/
**GET**: RETURN state.json

**POST**:  Execute postflight on target hosts, return state.json.

#### /api/v1/postflight/logs/
**GET**:  RETURN *_postflight.log files for download

#### /api/v1/success/
**GET**: RETURN url to DCOS UI

```
curl localhost:5000/api/v1/success
```
```json
{"dcosUrl": "http://foobar.com"}
```

# CLI Manpage

```pre
 ./run --help
usage: run [-h] [-v] [-p PORT] [-w | -c | -pre | -d | -pos | -vc | -t]

Install DCOS on-premise

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Verbose log output (DEBUG).
  -p PORT, --port PORT  Web server port number.
  -w, --web             Run the web interface.
  -c, --configure       Execute the configuration generation (genconf).
  -pre, --preflight     Execute the preflight checks on a series of nodes.
  -d, --deploy          Execute a deploy.
  -pos, --postflight    Execute postflight checks on a series of nodes.
  -vc, --validate-config
                        Validate the configuration in config.yaml
  -t, --test            Performs tests on the dcos_installer application
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
  log_directory: /genconf/logs
```
