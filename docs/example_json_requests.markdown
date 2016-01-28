# Example JSON Requests
Mock requests to emulate API calls to the backend. 

## Create Configuration File

```
curl -XPOST -H 'application/json' -d@generate_config_example.json 10.33.2.20:9000/api/v1/configure
```

Generate Config Example JSON:
```json
{ 
  "master_list": ["10.0.0.1"],
  "agent_list": ["10.0.0.2"],
  "ssh_user": "vagrant",
  "superuser_username": "testuser",
  "superuser_password": "MUST BE HASH*",
  "exhibitor_zk_hosts": "10.0.0.3:2181",
  "ssh_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKCAQEA6NF8iallvQVp22WDkTkyrtvp9eWW6A8YVr+kz4TjGYe7gHzI\nw+niNltGEFHzD8+v1I2YJ6oXevct1YeS0o9HZyN1Q9qgCgzUFtdOKLv6IedplqoP\nkcmF0aYet2PkEDo3MlTBckFXPITAMzF8dJSIFo9D8HfdOV0IAdx4O7PtixWKn5y2\nhMNG0zQPyUecp4pzC6kivAIhyfHilFR61RGL+GPXQ2MWZWFYbAGjyiYJnAmCP3NO\nTd0jMZEnDkbUvxhMmBYSdETk1rRgm+R4LOzFUGaHqHDLKLX+FIPKcF96hrucXzcW\nyLbIbEgE98OHlnVYCzRdK8jlqm8tehUc9c9WhQIBIwKCAQEA4iqWPJXtzZA68mKd\nELs4jJsdyky+ewdZeNds5tjcnHU5zUYE25K+ffJED9qUWICcLZDc81TGWjHyAqD1\nBw7XpgUwFgeUJwUlzQurAv+/ySnxiwuaGJfhFM1CaQHzfXphgVml+fZUvnJUTvzf\nTK2Lg6EdbUE9TarUlBf/xPfuEhMSlIE5keb/Zz3/LUlRg8yDqz5w+QWVJ4utnKnK\niqwZN0mwpwU7YSyJhlT4YV1F3n4YjLswM5wJs2oqm0jssQu/BT0tyEXNDYBLEF4A\nsClaWuSJ2kjq7KhrrYXzagqhnSei9ODYFShJu8UWVec3Ihb5ZXlzO6vdNQ1J9Xsf\n4m+2ywKBgQD6qFxx/Rv9CNN96l/4rb14HKirC2o/orApiHmHDsURs5rUKDx0f9iP\ncXN7S1uePXuJRK/5hsubaOCx3Owd2u9gD6Oq0CsMkE4CUSiJcYrMANtx54cGH7Rk\nEjFZxK8xAv1ldELEyxrFqkbE4BKd8QOt414qjvTGyAK+OLD3M2QdCQKBgQDtx8pN\nCAxR7yhHbIWT1AH66+XWN8bXq7l3RO/ukeaci98JfkbkxURZhtxV/HHuvUhnPLdX\n3TwygPBYZFNo4pzVEhzWoTtnEtrFueKxyc3+LjZpuo+mBlQ6ORtfgkr9gBVphXZG\nYEzkCD3lVdl8L4cw9BVpKrJCs1c5taGjDgdInQKBgHm/fVvv96bJxc9x1tffXAcj\n3OVdUN0UgXNCSaf/3A/phbeBQe9xS+3mpc4r6qvx+iy69mNBeNZ0xOitIjpjBo2+\ndBEjSBwLk5q5tJqHmy/jKMJL4n9ROlx93XS+njxgibTvU6Fp9w+NOFD/HvxB3Tcz\n6+jJF85D5BNAG3DBMKBjAoGBAOAxZvgsKN+JuENXsST7F89Tck2iTcQIT8g5rwWC\nP9Vt74yboe2kDT531w8+egz7nAmRBKNM751U/95P9t88EDacDI/Z2OwnuFQHCPDF\nllYOUI+SpLJ6/vURRbHSnnn8a/XG+nzedGH5JGqEJNQsz+xT2axM0/W/CRknmGaJ\nkda/AoGANWrLCz708y7VYgAtW2Uf1DPOIYMdvo6fxIB5i9ZfISgcJ/bbCUkFrhoH\n+vq/5CIWxCPp0f85R4qxxQ5ihxJ0YDQT9Jpx4TMss4PSavPaBH3RXow5Ohe+bYoQ\nNE5OgEXk2wVfZczCZpigBKbKZHNYcelXtTt/nP3rsCuGcM4h53s=\n-----END RSA PRIVATE KEY-----",
  'ip_detect_script': "#!/usr/bin/env bash\nset -o nounset -o errexit\nexport PATH=/usr/sbin:/usr/bin:$PATH\necho $(ip addr show eth0 | grep -Eo '[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}' | head -1)"
}
```

**PASSWORD**: You must use a hashed password, you can create one on the CLI with:

```dcos_installer --hash-password my$trong*w```

**SSH KEY**: You must use a valid SSH key for your nodes

**IP DETECT SCRIPT**: You should test this on your nodes before assuming it works!

**On Success**:

```json
{}
```

**On Failure**:

```json
{"master_list": "10.0.0.1 is not of type list.", "agent_list": "10.0.0.2 is not of type list."}
```

## Generate Packages & Begin Preflight

```
curl -XPOST 10.33.2.20:9000/api/v1/action/preflight
```

This will attempt to build configuration packages using `gen.generate()` and then kick off preflight.

**On Success**:
```json
{}
```

**On Failure**:
```json
{"errors": "Configuration generation failed, please see command line for details"}
```

### Check Preflight

```
curl -XGET 10.33.2.20:9000/api/v1/action/preflight
```

## Begin Deploy

```
curl -XPOST 10.33.2.20:9000/api/v1/action/deploy
```

**On Success**:

```json
{"status": "retry ['deploy_master', 'deploy_agent'] started"}
```

**On Failure**:

```json
{"status": "deploy was already executed, skipping"}
```

### Check Deploy

```
curl -XGET 10.33.2.20:9000/api/v1/action/deploy
```

**Example Response**:

```json
{
    "chain_name": "deploy",
    "hosts": {
        "10.0.0.1:22": {
            "commands": [
                {
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
                        "vagrant@10.0.0.1",
                        "sudo",
                        "mkdir",
                        "-p",
                        "/opt/dcos_install_tmp"
                    ],
                    "date": "2016-01-28 21:19:49.939101",
                    "pid": 8965,
                    "returncode": 255,
                    "stderr": [
                        "ssh: connect to host 10.0.0.1 port 22: Connection timed out\r",
                        ""
                    ],
                    "stdout": [
                        ""
                    ]
                }
            ],
            "host_status": "failed",
            "tags": {
                "role": "master"
            }
        },
        "10.0.0.2:22": {
            "commands": [
                {
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
                        "vagrant@10.0.0.2",
                        "sudo",
                        "mkdir",
                        "-p",
                        "/opt/dcos_install_tmp"
                    ],
                    "date": "2016-01-28 21:19:49.978304",
                    "pid": 8966,
                    "returncode": 255,
                    "stderr": [
                        "ssh: connect to host 10.0.0.2 port 22: Connection timed out\r",
                        ""
                    ],
                    "stdout": [
                        ""
                    ]
                }
            ],
            "host_status": "failed",
            "tags": {
                "role": "agent"
            }
        }
    },
    "total_agents": 1,
    "total_hosts": 2,
    "total_masters": 1
}
```

### Determine When Complete
When `total_hosts` == JSON[$IPADDRESS][0-9]['failed'] + JSON[$IPADDRESS][0-9]['success'] The run is complete. The JSON will update as SSH session runs asynchronously.

## Begin Postflight

```
curl -XPOST 10.33.2.20:9000/api/v1/action/postflight
```

**On Success**:

```json
{"status": "postflight started"}
```

### Check Postflight

```
curl -XGET 10.33.2.20:9000/api/v1/action/postflight
```

**Example Response**:

```json
{
    "chain_name": "postflight",
    "hosts": {
        "10.0.0.1:22": {
            "commands": [
                {
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
                        "vagrant@10.0.0.1",
                        "sudo",
                        "mkdir",
                        "-p",
                        "/opt/dcos_install_tmp"
                    ],
                    "date": "2016-01-28 21:30:28.195081",
                    "pid": 9088,
                    "returncode": 255,
                    "stderr": [
                        "ssh: connect to host 10.0.0.1 port 22: Connection timed out\r",
                        ""
                    ],
                    "stdout": [
                        ""
                    ]
                }
            ],
            "host_status": "failed",
            "tags": {
                "role": "master"
            }
        },
        "10.0.0.2:22": {
            "commands": [
                {
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
                        "vagrant@10.0.0.2",
                        "sudo",
                        "mkdir",
                        "-p",
                        "/opt/dcos_install_tmp"
                    ],
                    "date": "2016-01-28 21:30:28.202264",
                    "pid": 9089,
                    "returncode": 255,
                    "stderr": [
                        "ssh: connect to host 10.0.0.2 port 22: Connection timed out\r",
                        ""
                    ],
                    "stdout": [
                        ""
                    ]
                }
            ],
            "host_status": "failed",
            "tags": {
                "role": "agent"
            }
        }
    },
    "total_hosts": 2
}
```
## Success
When the postflight runs successfully, you can test the endpoint with:

```
curl -XGET 10.33.2.20:9000/api/v1/success
```

**Example Response**:

```json
{"master_count": 1, "agent_count": 1, "success": "http://10.0.0.1"}
```

However, this step is probably unneccessary as we should be running the integration test script which waits to determine if the cluster is in a running state. We should execute `action/postflight` after that step to ensure it's working as expected.

