defaults = {
  "resolvers": "[\"8.8.8.8\"]"
}

# TODO(cmaloney): GCE, Azure
implies = {
    "exhibitor_storage_backend": {
        "aws_s3": "onprem-exhibitor-aws",
        "zookeeper": "onprem-exhibitor-zk",
        "shared_filesystem": "onprem-exhibitor-fs"
    },
    "master_discovery": {
      "lb": "onprem-lb",
      "vrrp": "onprem-keepalived"
    }
}
