# Restart module + helper

Restarts + process management is handled through systemd for simplicity of implementation for now..

## Restart Steps

The restart module knows how to restart mesos cleanly
1. Have pkgpanda validate the new active config options are good
1. Run pkgpanda activate to activate new packages
1. Stop mesos
1. Wipe out work directory if requested "clean" / killall
1. Start mesos
  - If mesos fails to start
    1. `pkgpanda activate active.json.old`
    1. Start mesos
      - if mesos fails to start
        1. Report "HARD FAILURE/NODE LOST" to deployer, sysadmin introvention needed.
    1. Report "Soft failure" to deployer.
1. Ping deployer when the slave is up successfully
