# dcos-history-server
Collects and historicizes mesos state.

## Setup 

Python virtualenv is used for the project. You can set it up with
```make setup``` 
This will install a python interpreter with all the project dependencies.

## Packaging

Docker is used to build and package this service.
```make dist```

To push this package to dockerhub use
```make push```

The tag of this docker image is taken from the history version (see file `history/__init__`).
Please increment the version, if you push a new version.

## Running

To run the docker image on the local machine, you have to define all environment variables and then
 ```make run```

## Deploy via marathon

There is a marathon.json file suitable for the ovh cluster.
This file can be used as template.
To deploy on ovh use
```make ovh```


## Environment Variables

- `MASTER_URLS`: comma separated list of all masters. Default: http://master.mesos:5050
- `PORT`: the http port to bind to. Default: 5055
- `FETCH_FREQUENCY`: the frequency to fetch leader state [0..60]. Default: 2
```
MASTER_URLS=http://srv1:5050,http://srv2:5050,...,http://srvn:5050
PORT=5055 
FETCH_FREQUENCY=2
```

