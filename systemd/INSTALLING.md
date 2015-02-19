# Initial host setup

Copy to `/etc/systemd/system`:
 - dcos-bootstrap.service
 - dcos-download.service

Copy to `/etc/systemd/system/multi-user.target.wants/`:
 - dcos.target



*NOTE*: All of this config lives outside of /opt/mesosphere for dcos-download.service to work right, as well as alll of /opt/mesosphere to be filled in by extracting the dcos distribution.


## Bootstrap configuration

 - package list from active master when bootstrapping
   ```
   /etc/dcos/bootstrap-flags/repository-url
   /etc/dcos/bootstrap-flags/masters
   ```

 - Enable mesos master

   `/etc/dcos/roles/master`

 - Enable mesos slave

   `/etc/dcos/roles/slave`

# Required files inside of the dcos tarball
```
/bin/pkgpanda
/environment
```


# How it works

`dcos.target` depends upon `dcos-bootstrap.service`. `dcos-bootstrap.service` depends on
`dcos-download.service`

`dcos.target` is put into `/etc/systemd/system/multi-user.target.wants` so that is started
up by systemd when the machien boots. Systemd sees it has dependencies, and executes those
before it tries starting dcos.target.

`dcos-download.service` when run downloads the dcos tarball and extracts it onto the host
filesystem.

`dcos-bootstrap.service` runs pandapkg which will put all the bits into the right place / activate the packages on the
host, updating the set of packages if required (From the initial install of dcos a specific mesos module was added to the
configuration and must be loaded before a new slave is started).

