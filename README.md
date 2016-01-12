# DCOS Installer

## Run locally

1. ```pip install -r requirements.txt```
2. ```./run --web```

^^ Check the run script to ensure current stable BOOTSTRAP_ID, this was last set to the stable CM.4 bootstrap ID.

# REST API

#### / -redirects-> /api/v1
**GET**: Loads application

#### /api/v1/configure/
**GET**: Get currently stored configuration and validation messages.

```json
{
  "ssh_config": {
    "ssh_user": null,
    "target_hosts": [
      null
    ],
    "log_directory": "/genconf/logs",
    "ssh_key_path": "/genconf/ssh_key",
    "ssh_port": 22
  },
  "cluster_config": {
    "docker_remove_delay": "1hrs",
    "resolvers": [
      "8.8.8.8",
      "8.8.4.4"
    ],
    "roles": "slave_public",
    "exhibitor_storage_backend": "zookeeper",
    "ip_detect_path": "/genconf/ip-detect",
    "exhibitor_zk_hosts": "127.0.0.1:2181",
    "cluster_name": "Mesosphere: The Data Center Operating System",
    "weights": "slave_public=1",
    "num_masters": null,
    "master_discovery": "static",
    "master_list": null,
    "bootstrap_url": "file:///opt/dcos_install_tmp",
    "exhibitor_zk_path": "/exhibitor",
    "gc_delay": "2days"
  },
}
```

**POST**: Read config from disk, overwrite the POSTed values, validate, write to disk if no errors, only return errors if there are any.

```
curl -H 'Content-Type: application/json' -XPOST -d '{"ssh_config":{"ssh_user": "some_new_user"}}' localhost:5000/api/v1/configure | json
```

**SUCCESS** - 200, empty body

**FAILURE** - 400, errors
```json
{ "errors": {
   "ssh_user": "None is not a valid string. Is of type <class 'NoneType'>.",
   "target_hosts": "[None] is not valid IPv4 address.",
   "ssh_key_path": "File does not exist /genconf/ssh_key",
   "master_list": "None is not of type list."
  }
}
```

#### /api/v1/configure/status
**GET**: Get the current configuration validation

```
curl -H 'Content-Type: application/json' -XGET localhost:5000/api/v1/configure | json
```

```json
{
  "success": {
    "docker_remove_delay": "1hrs is a valid string.",
    "resolvers": "['8.8.8.8', '8.8.4.4'] is a valid list of IPv4 addresses.",
    "ssh_port": "22 is a valid integer.",
    "ip_detect_path": "File exists /genconf/ip-detect",
    "exhibitor_storage_backend": "exhibitor_storage_backend is valid.",
    "roles": "slave_public is a valid string.",
    "exhibitor_zk_hosts": "127.0.0.1:2181 is valid exhibitor ZK hosts format.",
    "cluster_name": "Mesosphere: The Data Center Operating System is a valid string.",
    "bootstrap_url": "file:///opt/dcos_install_tmp is a valid string.",
    "master_discovery": "master_discovery method is valid.",
    "weights": "slave_public=1 is a valid string.",
    "ssh_user": "some_new_user is a valid string.",
    "exhibitor_zk_path": "/exhibitor is a valid string.",
    "gc_delay": "1hrs is a valid string."
  },
  "warning": {},
  "errors": {
    "target_hosts": "[None] is not valid IPv4 address.",
    "ssh_key_path": "File does not exist /genconf/ssh_key",
    "master_list": "None is not of type list."
  }
}
```

Notice that the ssh_user is no longer ```None``` and the validation for it now passes since it is a string.

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
{
  "dcosUrl": "http://foobar.com",
  "master_count": 3,
  "agent_count": 400
}
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
  # Default: localhost
  bootstrap_url: localhost

  # The name of the DCOS cluster
  # Default: Mesosphere: The Data Center Operating System
  cluster_name: 'Mesosphere: The Data Center Operating System'

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

  # The master discovery method
  # Default: static list (master_list)
  master_discovery: static

  # The list of target hosts that will run Mesos Masters
  # Default: []
  master_list:
  - 10.33.2.20
  - 10.0.0.2
  - 10.0.0.3

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
