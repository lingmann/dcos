# Deploy Library
This library wraps the SSH library to enable genconf to remotely install DCOS to a distribtued cluster of target hosts.

## API Usage 
This is a purpose-driven library designed around the needs of genconf and enabling remote deployment via `dcos_generate_config.sh`. 

### validate.py
Tests the SSH conenction to target hosts by opening a simple SSH connection and executing `exit` on the remote machine. 

The exit code is logged in the target hosts log file and structured data about the run is returned to the caller. 

#### Arguments Accepted

```
`config` | Expects the configuration file for DCOS as a pythonic dictionary.
```

### copy.py
Executes SCP of `local_path` to 'remote_path' on target hosts. Primary uses of it would be to copy the bootstrap tarball for DCOS to 
remote hosts.

#### Arguments Accepted

```
`config`        | Expects the configuration file for DCOS as a pythonic dictionary.

`local_path`    | The path to the local file to copy to the remote host.

`remote_path`   | The path on the remote host to copy the file to.
```


### preflight.py
The preflight library copies the the preflight.sh to the remote machine and executes the script. It then ingests STDOUT to structured data 
that follows our structured log file output in the SSH library. 

#### Arguements Accepted

```
`config`        | Expects the configuration file for DCOS as a pythonic dictionary.

```

### deploy.py

#### Arguments Accepted


### Callable Bash Scripts
The bash scripts present in this library are used to run pre and post flight checks on DCOS infrastructure.

These scripts follow a standardized convention of dropping "PASS"|"FAIL"::"$MESSAGE" to STDOUT to enable easily parsing the bash
output into structured log data.

`preflight.sh`:

```bash
[root@test deploy]# ./preflight.sh
"PASS"::"DCOS currently installed?"
"FAIL"::"docker exists?"
"FAIL"::"docker version 0 acceptable?"
"PASS"::"curl exists?"
"PASS"::"bash exists?"
"PASS"::"ping exists?"
"PASS"::"tar exists?"
"PASS"::"xz exists?"
"FAIL"::"unzip exists?"
"PASS"::"systemctl exists?"
"PASS"::"systemctl version 208 acceptable?"
"FAIL"::"group 'nogroup' exists?"
"PASS"::":80 open? (required by mesos-ui)"
"PASS"::":53 open? (required by mesos-dns)"
"PASS"::":15055 open? (required by dcos-history)"
"PASS"::":5050 open? (required by mesos-master)"
"PASS"::":2181 open? (required by zookeeper)"
"PASS"::":8080 open? (required by marathon)"
"PASS"::":3888 open? (required by zookeeper)"
"PASS"::":8181 open? (required by exhibitor)"
"PASS"::":8123 open? (required by mesos-dns)"
```

`postflight.sh`:

```bash
# Example output TODO
```
