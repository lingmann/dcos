# Configuration package generation

TODO(cmaloney): Needs product decisions

Give a pretty UI which will generate a config tarball, and allow you to
seamlessly deploy it to your cluster on demand.

TODO(cmaloney): General mesos config (isolators, resources, etc)

TODO(cmaloney): Targeting config at a subset of hosts

## Modules

Upon enabling a module the config needs to do a couple pieces
 - Add a `requires` on that module's package
 - Add a fetch package step to fetch the module
 - Add paths to the .so files inside of the
 - Add the list of module names to actually enable inside the shared library.
 - Introspect the module to see what the available flags / parameters which might
   be interesting to show users are.
