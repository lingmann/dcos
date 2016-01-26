# Manual DCOS Installation on the CLI
This document describes how to install DCOS on the CLI via manual deployment. 

## Prerequisits
### Installer Host
1. Install Docker

```
# Install docker..
```
2. Download dcos_generate_config.sh

```
# curl http://mesosphere.downloads.com/...
```
3. Download NGINX docker container or other server to distribute the DCOS installation package

```
# docker pull nginx...
```

In order to manually distribute the DCOS cluster packages you must provide a server to expose to the ```bootstrap_url``` in the config.yaml file. The dcos_install.sh will be populated with this server's URL to curl the built configuration after you generate it in another step.
  
4. Setup a backend to share exhibitor bootstrap file.
  - We use a tool called Exhibitor to bootstrap your DCOS Zookeeper cluster. Exhibitor manages and automates the Zookeeper bootstrapping process. Exhibitor itself needs a way to share it's configuration between nodes. The most popular way to do this is standup a second zookeeper quarum but you can also use the shared filesystem (if you have NFS between hosts) or AWS S3:
    - Zookeeper
    - Shared Filesystem
    - AWS S3
   
### Cluster Host
TODO: Cluster prereqs

## Create Configuration File
TODO: Link to config-manual-distro.markdown

## Create ip-detect Script
TODO: Link to ip-detect.markdown

## Execute Configuration Generation

## Distribute DCOS Artifacts to Cluster Manually
