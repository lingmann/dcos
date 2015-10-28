# DOCS Installer
Flask implementation

## Run locally

1. ```pip install -r requirements.txt```
2. ```./run_dcos_installer```

## Manpage

**NAME**

run_dcos_installer -- run the DCOS installer

**SYNOPSIS**

run_dcos_installer [ -l | --log-level ] [ -p | --port ] [ -m | --mode ] [ -c | --config-path ] [ -d | --install-directory ]

**DESCRIPTION**

The DCOS installer runs a web or CLI utility to build DCOS configuration files for your cluster and exposes several deployment options.

**FLAGS**
  
  -c | Configuration Path - Set the configuration path, default is $HOME/dcos/dcos-config.yaml: Accepts a valid /path/to/config.yaml.

  -d | Install Directory - Set hte configuration directory used to store and build the bootstrap tarball, defaults to $HOME/dcos: Accepts a valid /path/to/install/stuff. 
  
  -l | Log Level - Set the loglevel: 'info' or 'debug'

  -m | Mode - Set the isntaller mode, defualt is 'web': 'non-interactive' or 'web'

  -p | Port - Override the default port of :5000. Accepts an integer.
  
    
