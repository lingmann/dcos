import logging

from dcos_installer.config import DCOSConfig

log = logging.getLogger(__name__)

mock_action_state = {
    "127.0.0.1:22022": {
        "commands": [
            {
                "cmd": [
                    "/usr/bin/ssh",
                    "-oConnectTimeout=10",
                    "-oStrictHostKeyChecking=no",
                    "-oUserKnownHostsFile=/dev/null",
                    "-oBatchMode=yes",
                    "-oPasswordAuthentication=no",
                    "-p22022",
                    "-i",
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@127.0.0.1",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:42.773561",
                "pid": 20785,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 127.0.0.1 port 22022: Connection refused\r",
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
    "52.35.180.142:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.35.180.142",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:53.508197",
                "pid": 20800,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.35.180.142 port 22: Operation timed out\r",
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
    "52.35.203.104:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.35.203.104",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:53.167311",
                "pid": 20799,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.35.203.104 port 22: Operation timed out\r",
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
    "52.35.209.217:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.35.209.217",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:43.486630",
                "pid": 20797,
                "returncode": 255,
                "stderr": [
                    "Warning: Permanently added '52.35.209.217' (ECDSA) to the list of known hosts.\r",
                    "Permission denied (publickey).\r",
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
    "52.35.209.2:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.35.209.2",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:53.150617",
                "pid": 20798,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.35.209.2 port 22: Operation timed out\r",
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
    "52.35.249.172:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.35.249.172",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:53.109791",
                "pid": 20796,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.35.249.172 port 22: Operation timed out\r",
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
    "52.88.115.240:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.115.240",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:52.775261",
                "pid": 20790,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.88.115.240 port 22: Operation timed out\r",
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
    "52.88.220.149:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.220.149",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:43.091281",
                "pid": 20789,
                "returncode": 255,
                "stderr": [
                    "Warning: Permanently added '52.88.220.149' (ECDSA) to the list of known hosts.\r",
                    "Permission denied (publickey,password).\r",
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
    "52.88.231.115:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.231.115",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:43.125068",
                "pid": 20787,
                "returncode": 255,
                "stderr": [
                    "Warning: Permanently added '52.88.231.115' (ECDSA) to the list of known hosts.\r",
                    "Permission denied (publickey,password).\r",
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
    "52.88.231.59:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.231.59",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:52.774169",
                "pid": 20788,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.88.231.59 port 22: Operation timed out\r",
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
    "52.88.249.230:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.249.230",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:52.765248",
                "pid": 20786,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.88.249.230 port 22: Operation timed out\r",
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
    "52.88.25.18:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.25.18",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:43.154439",
                "pid": 20795,
                "returncode": 255,
                "stderr": [
                    "Warning: Permanently added '52.88.25.18' (ECDSA) to the list of known hosts.\r",
                    "Permission denied (publickey).\r",
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
    "52.88.28.76:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.28.76",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:52.786028",
                "pid": 20794,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.88.28.76 port 22: Operation timed out\r",
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
    "52.88.49.130:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.49.130",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:52.785151",
                "pid": 20793,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.88.49.130 port 22: Operation timed out\r",
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
    "52.88.60.147:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.60.147",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:52.784125",
                "pid": 20792,
                "returncode": 255,
                "stderr": [
                    "ssh: connect to host 52.88.60.147 port 22: Operation timed out\r",
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
    "52.88.91.74:22": {
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
                    "/Users/mnaboka/mesos/keys/mesosphere_shared_develoer_infrostructure_aws.pem",
                    "ec2-user@52.88.91.74",
                    "uname",
                    "-a"
                ],
                "date": "2016-01-15 10:01:43.133815",
                "pid": 20791,
                "returncode": 255,
                "stderr": [
                    "Warning: Permanently added '52.88.91.74' (ECDSA) to the list of known hosts.\r",
                    "Permission denied (publickey,password).\r",
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
    "chain_name": "mnaboka",
    "hosts_failed": 16,
    "total_hosts": 30
}


def validate():
    """
    Take the new data from a post, add it to base defaults if overwritting them
    and validate the entire config, return messages.
    If the new_data is empty, return the pure defualts for the config. This is in
    place of having a known file system that we're writing to for config.yaml, in
    which case we'd pass the config_path option to DCOSConfig so it uses those
    instead of the defualts. For now, the mock version will return only defualts
    on GET and return the complete config with overrides on POST.
    """
    config = DCOSConfig()
    messages = config.validate()
    return messages
