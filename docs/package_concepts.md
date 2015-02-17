# Package concepts

*Package Name*: The name which other packages will know this package by, used so that. Package names must be valid linux folder names, are case insensitive / always lower case, may not contain '@'.

*Package ID*: `package-name@foobar` Combination package name + arbitrary other information (likely some sort of version indicator). The packaging system just cares that it can extract the package name from a package id, as well as can fetch the package from

## Install directories

The packaging system makes use of some *well-known directories*. Well-known directories are used so that packages can find information from other packages without having to know the exact package version some piece is coming from.


## Package

Well-known directories which packages can depend upon. All other filesystem directories should be assumed to not exist.

Different things want to rely on finding certain packages at certain locations. When we unbundle things, there are often multiple components which are shipped independently (So we can update java without having to re-ship everything). In order for all the java packages to find the "current java" we need to make java at a well known location.


# Why /opt/mesosphere/config, etc.

 Not all packages know what is going to provide bits of environment. Mesos shouldn't need to know for instance what is the name of the package which provides hdfs, it just cares if hdfs is available.

 This goes for config as well, I might want to have a monolithic mesos-config package name, or a bunch of small {mesos-slave-config, mesos-master-config} packages. Either way mesos needs to be able to find the config.

 ## The special directories, files, and their contents

 ### Special install files + directories
/opt/mesosphere/environment
  - All the environment variables to be used when running mesos. Compiled from
  'environment' files inside of any package as well as a generated PATH and LD_LIBRARY_PATH containing the /opt/mesosphere/bin and /opt/mesosphere/lib
/opt/mesosphere/bin/
/opt/mesosphere/lib/
/opt/mesosphere/etc/
/opt/mesosphere/active/{name}/
/opt/mesosphere/packages/{id}/
/etc/systemd/system/dcos.target/

### Assumed system files
/etc/systemd/system/multi-user.target/dcos.target


## Reasoning
Why don't we do /{name}/current
  - Then we can't atomically swap things into place, easier to get partial updates.

Why not make /{name}/{id-without-name}
  - Who cleans up /{name}/?
  - Lots more logic.

When things go wrong, how to recover
1) Dump the host and load a new one, simplest safest
2) Re-bootstrap with packager
3) packager activate {list of packages}
    - Fix problems if they happen

NOTE: Packager should always overwrite / remove / replace .new when that is given.


TODO: Doc how we support upgrading things in light of security problems.
