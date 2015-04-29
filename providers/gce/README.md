# gce-provisioner

Mesos GCE provisioning library, a partner to the [aws-provisioner]
(https://github.com/mesosphere/aws-provisioner).

## Goals

- It **must** be done using [Deployment Manager v2 templates](https://cloud.google.com/deployment-manager/overview)

- It **must** use the same images and cloudconfig that AWS and Azure use.

- *User* **must** be able to connect to the cluster via the DCOS CLI 
  (this is the only way to interact with the cluster).

- It must be in the [Click2Deploy marketplace](https://cloud.google.com/solutions/mean/click-to-deploy) 
  (this will happen via Google once we have `DMv2` templates for them that work).

- *User* **must** be able to resize  cluster via the command line.


## Releases

### Beta EA - 2015-May-06

DCOS ready to be reviewed by Google staff for possible demoing at Velocity Conference (5/27)

### Beta Release - 2015-May-27

Following demo and public release, made available to GCE users.

### DCOS on GCE v. 1.0 - TBD

Stable release availabe on [Click2Deploy marketplace](https://cloud.google.com/solutions/mean/click-to-deploy)

## Configuration and Setup

```
TODO: Instructions go here
```

## Components

## Testing

To test that your ``config.yml`` and the associated templates can be correctly
expanded by DMv2, execute the following::

    $ gcloud preview dm-v2 manifests --deployment foo expand --config config.yml 

where the name of the deployment is irrelevant, and ``config.yml`` is the template
you are testing.

See ``examplets/config.yml`` in this repo for an example.

## Run example

To setup credentials, you will need to create new client ID and client secret
for your GCE project. 

Visit the [Google Developers Console](TODO: link goes here), open your project.
Then choose ``Credentials`` tab and click ``create new Client ID``

Once the application is created, download the JSON file. 
Save this file as *client_secrets.json*.

Add path to *client_secrets.json* file to ```config.yaml.example``` file,
also edit, if it is needed, other parameters in ```config.yaml.example``` file.

Create a virtualenv for the project:
```
make env
```

Activate enviroment:
```
source env/bin/activate
```

Run ```create_group.py``` file to create new GCE cluster.
```
python examples/create_group.py`
```

```
TODO: either links to other projects and/or a description of the components go here
```
