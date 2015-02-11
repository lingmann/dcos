# Package format

Packages are tarballs which contain a basic manifest, 'usage.json' describing
the contents.

TODO(cmaloney): Packages should announce themselves as attributes on slaves.

# usage.json format

Usage.json contains a json dictionary. Extra keys are ignored. Below are the
well-defined keys

**provides**: String. Only one package which provides a given name may be activated
at a time.

**executables**: List of strings. Each string is the path to a binary inside of
the package which should be available to other binaries on the host. The binaries
get a symlink from /opt/mesosphere/bin

**environment**: List of environment variables to add to the default system
environment. The environm

**systemd**: List of systemd unit files which need to be installed + enabled by
systemd when the package is activated.

**conf**: List of files which should be installed to well known paths. All
config will go in /opt/mesosphere/config/{provides}/

**requires**: List of packages which must be activated at the same time as this
package. The package manager will never auto-activate packages or do anything
other than reject a configuration based on this information.

# Well known packages
Some provides kinds have more formal specification for how they work together:

## mesos-systemd, mesos, mesos-config
