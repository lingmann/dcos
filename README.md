# DCOS Installer

### DISABLE SENDFILE SUBSYSTEM
Sendfile sub system for serving static assets was caching / appending weird binary data to the end of our index.js. To prevent aiohttp from using the sendfile subsystem you must do export this ENV var:

```export AIOHTTP_NOSENDFILE=1export AIOHTTP_NOSENDFILE=1```

## Run locally

1. ```pip install -r requirements.txt```
2. ```python setup.py develop```
3. ```source test_env```
4. ```dcos_installer --web```

## Build the UI Assets

1. Install nodejs and npm - OS dependant, on OSx you can use Brew


Note: depending on what features in dcos-image are being used, some of the dummy environment variables mmay need to be populated with valid values

## Compile Frontend Assets

1. Install NodeJS version `4.2.5` (it is helpful to use a node version manager like [nvm](https://github.com/creationix/nvm) or [n](https://github.com/tj/n)). This should come with NPM version `2.4.12`
2. Change directory to `/ui/`
3. Install dependencies by executing the command `npm install`
4. Transpile JavaScript and CSS assets by executing the command `./node_modules/.bin/gulp dist`
5. Transpiled files will be placed in `/dcos_installer/templates` which will be served by the Python web server.

## Run from artifacts

1. Go to https://teamcity.mesosphere.io/viewType.html?buildTypeId=ClosedSource_Dcos_Installer_OnPremInstallerCreation
2. Find a desired build and download the installer from the artifacts drop-down, or trigger a custom build ("..." next to run) and specify the dcos-image version under Dependencies and the dcos-installer version under Changes
3. ```bash dcos_installer.sh``` will run the web installer application.
4. To debug and introspect the installer script, any arguments given will be passed to the docker container as the container command (default docker entrypoint)

## Build artifacts
setup.py can also package the repo as a self-loading docker image within a bash script:
1. ```pip install -r requirements.txt```
2. ```pip setup.py build_docker```
NOTE: the following environment variables will need to be set for full functionality
* DCOS_INSTALLER_COMMIT
* DCOS_IMAGE_COMMIT
* CHANNEL_NAME
* BOOTSTRAP_ID

# REST API

#### / -redirects-> /api/v1
**GET**: Loads application

#### /assets
**GET**: Serves assets in dcos_installer/assets/

Return headers are self informed. In example, if the file is foo.js the header to return will be ```application/javascript```. 

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

Example POST data structure:

```json
{
  "master_ips": ["...", "..."],
  "agent_ips": ["...", "..."],
  "ssh_username": "...",
  "ssh_port": 22,
  "ssh_key": "...",
  "username": "...",
  "password": "...",
  "upstream_dns_servers": "..."
  "zk_exhibitor_port": ".." # Yes, it's a string please!
  "zk_exhibitor_hosts": ["...", "..."]
  "ip_detect_script": "..."
}
```

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


#### /api/v1/configure/type
**GET**: Get the current configuration type, advanced or minimal.

If minimal is found:
```json
{
  "configuration_type": "minimal",
  "message": "Configuration looks good!",
}
```

If advanced is found:
```json
{
  "configuration_type": "advanced",
  "message": "Advanced configuration detected in genconf/config.yaml. Please backup or remove genconf/config.yaml to use the UI installer."
}
```

#### /api/v1/action/preflight/
**GET**:  RETURN preflight_status.json

```
curl localhost:5000/api/v1/preflight | json
```
```json
{
  "chain_name": "preflight",
  "total_hosts": 2,
  "hosts_failed": 2,
  "hosts": {
    "10.33.2.21:22": {
      "host_status": "failed",
      "commands": [
        {
          "date": "2016-01-22 23:51:37.324109",
          "stdout": [
            ""
          ],
          "stderr": [
            "ssh: connect to host 10.33.2.21 port 22: No route to host\r",
            ""
          ],
          "pid": 3364,
          "cmd": [
            "/usr/bin/ssh",
            "-oConnectTimeout=10",
            "-oStrictHostKeyChecking=no",
            "-oUserKnownHostsFile=/dev/null",
            "-oBatchMode=yes",
            "-oPasswordAuthentication=no",
            "-p22",
            "-i",
            "/genconf/ssh_key",
            "-tt",
            "vagrant@10.33.2.21",
            "sudo",
            "mkdir",
            "-p",
            "/opt/dcos_install_tmp"
          ],
          "returncode": 255
        }
      ]
    },
    "10.33.2.22:22": {
      "host_status": "failed",
      "commands": [
        {
          "date": "2016-01-22 23:51:37.325893",
          "stdout": [
            ""
          ],
          "stderr": [
            "ssh: connect to host 10.33.2.22 port 22: No route to host\r",
            ""
          ],
          "pid": 3365,
          "cmd": [
            "/usr/bin/ssh",
            "-oConnectTimeout=10",
            "-oStrictHostKeyChecking=no",
            "-oUserKnownHostsFile=/dev/null",
            "-oBatchMode=yes",
            "-oPasswordAuthentication=no",
            "-p22",
            "-i",
            "/genconf/ssh_key",
            "-tt",
            "vagrant@10.33.2.22",
            "sudo",
            "mkdir",
            "-p",
            "/opt/dcos_install_tmp"
          ],
          "returncode": 255
        }
      ]
    }
  }
}
```

**POST**: Execute preflight on target hosts. Returns state.json

#### /api/v1/action/preflight/logs/
**GET**: Get *_preflight logs for download (this is a .tar file)

#### /api/v1/action/deploy/
**GET**:  RETURN state.json

**POST**: Execute install DCOS on target hosts. Return state.json.

#### /api/v1/action/deploy/logs/
**GET**: Get *_deploy.log data for download (this is a .tar file)

#### /api/v1/action/postflight/
**GET**: RETURN state.json

**POST**:  Execute postflight on target hosts, return state.json.

#### /api/v1/action/postflight/logs/
**GET**:  RETURN *_postflight.log files for download

#### /api/v1/action/current/
**GET**: RETURN current_action_name

```json
{
  "current_action": "postflight"
}
```

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
