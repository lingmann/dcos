# Google Cloud Templates

Mesos GCE provisioning templates are defined here and will use the
[Deployment Manager v2 templates](https://cloud.google.com/deployment-manager/overview)
format, and will eventually be used in the
[Click2Deploy marketplace](https://cloud.google.com/solutions/mean/click-to-deploy) 
configuration

## Goals

- It uses the general same templating generation and provisioning process that AWS and Azure use.

- *User* **must** be able to connect to the cluster via the DCOS CLI 
  (this is the only way to interact with the cluster).

- *User* **must** be able to resize  cluster via the command line.


## Testing

To test that your ``config.yml`` and the associated templates can be correctly
expanded by DMv2, execute the following::

    $ gcloud preview dm-v2 manifests --deployment test-me expand --config config.yml 

where the name of the deployment is irrelevant, and ``config.yml`` is the template
you are testing.

See ``config.yml`` in this repo for an example.

## Use the Template

To setup credentials, you will need to authenticate via ``gcloud`` for your GCE project::

    $ gcloud auth login

then setup the default ``project`` to use for your deployment and enable "preview" components::

    $ gcloud config set project PROJECT
    $ gcloud components update preview

finally, deploy the configuration::

    $ gcloud preview dm-v2 deployments create mesos-test --config templates/config.yml

See the [gcloud compute page](https://cloud.google.com/compute/docs/gcloud-compute/#auth) for
more details.
To login to instance, you can use gcloud command::

    $ gcloud compute ssh <mesos_instance_name> --zone <zone_name>

One important thing, please make sure, that your local machine public ip address is included
``admin_range`` parameter, in other case you will not have access to the instances.

For more information about DM, see [here](https://cloud.google.com/deployment-manager/create-first-deployment).


## Releases

### Beta EA - 2015-May-13

DCOS ready to be reviewed by Google staff and usable via the ``gcloud`` CLI utility.

### Beta Release - 2015-May-31

Available to GCE users via the [Click2Deploy marketplace](https://cloud.google.com/solutions/mean/click-to-deploy) 

### DCOS on GCE v. 1.0 - TBD

Stable release availabe on [Click2Deploy marketplace](https://cloud.google.com/solutions/mean/click-to-deploy)

## Configuration and Setup

See the [Common configuration](../../docs/common.rst) notes for the deployment properties' values
