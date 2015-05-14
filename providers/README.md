# DCOS Providers

Python script to gen provider-specific config for DCOS launches from common 
sources to prevent hand-dupliaction

## Requirements

python 3
 - On OSX you can get this with `brew install python3`


Python requirements: `jinja`, `docopt`

Installing with pip:
```
pip3 install jinja2
pip3 install docopt
```

## Vagrant Provider

`./gen.py vagrant testing/continuous cody --copy`

Will create a new single-node DCOS cluster named 'cody' based on the
`testing/continuous` release which is continually updated by teamcity based on 
the newest dcos-image master branch commit. The '--copy' makes it copy the 
`Vagrantfile` and `config.rb` which are cluster-agnostic into the folder rather
than just symlinking them. If you don't inted to change them, don't do --copy so
that they get the latest updates automatically as the repository is updated and
you do pulls.

Every branch in the dcos-image project creates a different 
'testing/{branch_name}' which you can use for development.

EarlyAcess, has the release name `EarlyAccess`.


### Run the cluster

Assuming your cluster is named 'cody':

`cd vagrant/cluster/cody && vagrant up`

The ui when it eventually comes up (Takes a while), will be at http://localhost:5080

## Debugging / watching it come up
```
vagrant ssh
journalctl -f
```

Things are up when the nginx starts / finds leader.mesos. Should take 15 minutes or less.
