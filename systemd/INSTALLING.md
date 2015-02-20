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

   # List of packages to activate
   /etc/dcos/bootstrap-flags/active
   ```

 - Enable mesos master

   `/etc/dcos/roles/master`

 - Enable mesos slave

   `/etc/dcos/roles/slave`

# Required files inside of the dcos tarball
```
/bin/pkgpanda
/environment
# These are activated based on the role.
# In general running the config package which is installed should have a 'systemd'
# folder which informs what systemd units to install to dcos.target.wants.
# But that isn't setup / enabled yet.
/active/mesos/bootstrap-systemd/mesos-master.service
/active/mesos/bootstrap-systemd/mesos-slave.service
```

TODO(cmaloney): Should we report status back to somewhere?

# How it works

`dcos.target` depends upon `dcos-bootstrap.service`. `dcos-bootstrap.service` depends on
`dcos-download.service`

`dcos.target` is put into `/etc/systemd/system/multi-user.target.wants` so that is started
up by systemd when the machien boots. Systemd sees it has dependencies, and executes those
before it tries starting dcos.target.

`dcos-download.service` when run downloads the dcos tarball and extracts it onto the host
filesystem.

`dcos-bootstrap.service` runs `pandapkg bootstrap` which will put all the bits into the right place / activate the packages on the host, updating the set of packages if required (From the initial install of dcos a specific mesos module was added to the
configuration and must be loaded before a new slave is started).

The `pandapkg bootstrap` will add a all the necessary systemd units to /etc/systemd/system/dcos.target.wants so they will be restarted on reboot, as well as performs a `systemctl daemon-reload` so systemd picks up the new target dependencies, and then a `systemctl start` to force the new targets to start.


## TODO old notes to be merged into above.
`pkgpanda` will use the seed url to download an initial list of "active"
packages. It will then fetch each of those packages and run a 'pkgpanda activate'.
The activate will
