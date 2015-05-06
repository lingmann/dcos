# Vagrant single-host DCOS

Getting the vagrant DCOS, making a vagrant box named dcos-test


Requirements: Python 3
 - OSX get with `brew install python`


Python requirements: `jinja`, `docopt`

Installing with pip:
```
pip3 install jinja2
pip3 install docopt
cd providers/vagrant
./make_cluster testing/continuous dcos-test
```

## Running it
`cd dcos-testgit pu && vagrant up`

The ui when it eventually comes up (Takes a while), will be at http://localhost:5080

## Debugging / watching it come up
```
vagrant ssh
jouranlctl -f
```

Things are up when the nginx starts / finds leader.mesos. Should take 15 minutes or less.