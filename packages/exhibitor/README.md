## Overview

This package provides [Exhibitor] and [Zookeeper] services for DCOS.

Exhibitor provides process supervision, configuration management, and a REST
API in front of a Zookeeper cluster. Zookeeper is a coordination service for
distributed applications.

In order to use this package, the following environment variables must be set
in the DCOS environment (via `/opt/mesosphere/etc/exhibitor` or
`/opt/mesosphere/etc/cloudenv`):

- ZOOKEEPER_CLUSTER_SIZE
- FALLBACK_DNS
- EXHIBITOR_HOSTNAME
- EXHIBITOR_WEB_UI_PORT

Along with a set of environment variables for the provider in use, either AWS:

- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_S3_BUCKET
- AWS_S3_PREFIX
- AWS_REGION

Or Azure:

- AZURE_ACCOUNT_NAME
- AZURE_ACCOUNT_KEY
- AZURE_PREFIX
- AZURE_CONTAINER

[exhibitor]: https://github.com/Netflix/exhibitor
[zookeeper]: http://zookeeper.apache.org/doc/current/
