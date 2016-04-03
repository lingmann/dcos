#!/usr/bin/env python3
"""
azure_test_driver

Usage:
    azure_test_driver deploy <state_file>
    azure_test_driver verify_template <state_file>
    azure_test_driver delete <state_file>

Template options are currently specified via environment variables:
    AZURE_PARAM_key=value  'key' is the template parameter name, 'value' treated as string
    AZURE_PARAM_INT_key    'key' is the template parameter name, 'value' treated as int
    AZURE_TEMPLATE_PATH    Set to the path of the ARM template
    AZURE_LOCATION         Set to the Azure location, defaults to 'East US'
    AZURE_PREFIX           Set to resource group prefix for easy identification, defaults to 'teamcity'
"""

import json
import os
import re
import subprocess
import sys
import traceback

import docopt
import pprint
import requests
from retrying import retry

from gen.azure.azure_client import (AzureClient, AzureClientException,
                                    AzureClientTemplateException,
                                    TemplateProvisioningState)


def verify_template_syntax(client, template_body_json, template_parameters):
    print("Verifying template ...")
    try:
        client.verify(template_body_json=template_body_json,
                      template_parameters=template_parameters)
    except AzureClientTemplateException as e:
        pprint.pprint(e)
        print("Template verification failed", file=sys.stderr)
        sys.exit(1)
    print("Template OK!")
    sys.exit(0)


def json_pretty_print(json_str, file=sys.stdout):
    print(json.dumps(json_str, sort_keys=True, indent=4, separators=(',', ':')), file=file)


def get_template_output(client):
    '''
    Returns the ARM deployment output values which has the format:
      {
        'output_key': {
          'value': 'output_value',
          'type': 'String'
        }
      }
    '''
    r = client.get_template_deployment()
    return r.get('properties', {}).get('outputs', {})


def get_template_output_value(template_output, *output_keys):
    '''
    Given a tuple of output_keys, return the value for the first matching key
    in template_output.  This is useful for testing templates which have
    different keys for the same output value. Raises an AzureClientException if
    none of the keys are found.
    '''
    for k in output_keys:
        if k in template_output:
            return template_output.get(k).get('value')
    raise AzureClientException("Unable to find any of the output_keys {} in deployment".format(output_keys))


def get_dcos_ui(master_url):
    try:
        return requests.get(master_url)
    except requests.exceptions.ConnectionError:
        pass


def retry_unless_azure_client_exception(exception):
    return not isinstance(exception, AzureClientException)


def get_env_params():
    '''
    Return ARM input template parameters populated based on environment variables. Parameters are set as follows:
      * AZURE_PARAM_key=value (value treated as a string)
      * AZURE_PARAM_INT_key=value (value treated as an int)
    '''
    template_params = {}
    env_param_regex = re.compile(r"AZURE_PARAM_(?P<param>.*)")
    env_param_int_regex = re.compile(r"AZURE_PARAM_INT_(?P<param>.*)")
    for env_key, env_val in os.environ.items():
        match_string = env_param_regex.match(env_key)
        match_int = env_param_int_regex.match(env_key)
        if match_int:
            template_params[match_int.group('param')] = {"value": int(env_val)}
        elif match_string:
            template_params[match_string.group('param')] = {"value": env_val}

    return(template_params)


def create_cluster(client, location, arm, template_params):
    '''
    Creates a new resource group, deploys a cluster within the resource group.
    Blocks until the cluster is successfully deployed.
    Returns template output parameters.
    '''
    # Create a new resource group
    print("Creating new resource group in location: {}".format(location))
    print(client.create_resource_group(location))

    # Actually create a template deployment
    print("Creating template deployment ...")
    deployment_response = client.create_template_deployment(
        template_body_json=arm,
        template_parameters=template_params)
    json_pretty_print(deployment_response)

    # For deploying templates, stop_max_delay must be long enough to handle the ACS template which does not signal
    # success until leader.mesos is resolvable.
    @retry(wait_fixed=(5*1000),
           stop_max_delay=(45*60*1000),
           retry_on_exception=lambda x: isinstance(x, AssertionError))
    def poll_on_template_deploy_status(client):
        provisioning_state = client.get_template_deployment()['properties']['provisioningState']
        if provisioning_state == TemplateProvisioningState.FAILED:
            failed_ops = client.list_template_deployment_operations(provisioning_state)
            raise AzureClientException("Template failed to deploy: {}".format(failed_ops))
        assert provisioning_state == TemplateProvisioningState.SUCCEEDED, \
            "Template did not finish deploying in time, provisioning state: {}".format(provisioning_state)

    print("Waiting for template to deploy ...")
    poll_on_template_deploy_status(client)

    print("Template deployed successfully")

    outputs = get_template_output(client)
    master_lb = get_template_output_value(outputs, 'dnsAddress', 'masterFQDN')

    print("Template deployed using SSH private key: https://mesosphere.onelogin.com/notes/18444")
    print("For troubleshooting, master0 can be reached using: ssh -p 2200 core@{}".format(master_lb))

    return(outputs)


def delete_cluster(client):
    '''
    Deletes the resource group.
    '''
    @retry(wait_exponential_multiplier=1000,
           wait_exponential_max=60*1000,
           stop_max_delay=(30*60*1000),
           retry_on_exception=retry_unless_azure_client_exception)
    def delete_resource_group(client):
        del_response = client.delete_resource_group()
        status_code = del_response.status_code
        if status_code == requests.codes.not_found:
            raise AzureClientException("Deployment not found")
        assert del_response.status_code == requests.codes.accepted, \
            "Delete request failed: {}".format(del_response.status_code)
        return del_response.headers['Location']

    print("Deleting resource group: {} ...".format(client._resource_group_name))
    poll_location = delete_resource_group(client)

    @retry(wait_fixed=(5*1000), stop_max_delay=(60*60*1000))
    def wait_for_delete(poll_location):
        r = client.status_delete_resource_group(poll_location)
        assert r.status_code == requests.codes.ok, "Timed out waiting for delete: {}".format(r.status_code)

    print("Waiting for delete ...")
    wait_for_delete(poll_location)

    print("Delete successful")


def run():
    try:
        arguments = docopt.docopt(__doc__)
    except docopt.DocoptExit as e:
        print(e)
        sys.exit(1)

    state_file = arguments['<state_file>']
    rg_prefix = os.getenv('AZURE_PREFIX', 'teamcity')
    template_path = os.environ['AZURE_TEMPLATE_PATH']
    arm = json.loads(open(template_path).read())
    location = os.getenv('AZURE_LOCATION', 'East US')
    template_params = get_env_params()
    deploy_successful = False

    print("Deploying with template parameters:")
    pprint.pprint(template_params)

    try:
        with open(state_file) as f:
            print("Reading existing state file: {}".format(state_file))
            cluster_state = json.load(f)
            rg = cluster_state['resource_group_name']
            dn = cluster_state['deployment_name']
            client = AzureClient.create_from_existing(resource_group_name=rg, deployment_name=dn)
    except IOError as e:
        client = AzureClient.create_from_env_creds(random_resource_group_name_prefix=rg_prefix)
        azure_cluster = {'resource_group_name': client._resource_group_name,
                         'deployment_name': client._deployment_name}
        print("Creating new state file: {}".format(state_file))
        open(state_file, mode='w').write(json.dumps(azure_cluster))

    resource_group = client._resource_group_name
    deployment = client._deployment_name

    # Output test cluster details
    print("Resource group: {}".format(resource_group))
    print("Deployment: {}".format(deployment))

    if arguments['deploy']:
        try:
            outputs = create_cluster(client, location, arm, template_params)
            master_url = 'http://{}'.format(get_template_output_value(outputs, 'dnsAddress', 'masterFQDN'))

#            @retry(wait_fixed=(5*1000), stop_max_delay=(15*60*1000))
#            def poll_on_dcos_ui_up(master_url):
#                r = get_dcos_ui(master_url)
#                assert r is not None and r.status_code == requests.codes.ok, \
#                    "Unable to reach DCOS UI: {}".format(master_url)
#
            print("Waiting for DCOS UI at: {} ...".format(master_url))
#            poll_on_dcos_ui_up(master_url)
            deploy_successful = True
        except (AssertionError, AzureClientException) as ex:
            print("ERROR: {}".format(ex), file=sys.stderr)
            traceback.print_tb(ex.__traceback__)

        logs = subprocess.check_output(['azure', 'group', 'log', 'show', resource_group, '--all'])
        open('{}.log'.format(state_file), mode='wb').write(logs)

        if deploy_successful:
            print("Azure test deployment succeeded")
            sys.exit(0)
        else:
            print("ERROR: Azure test deployment failed", file=sys.stderr)
            sys.exit(1)

    if arguments['verify_template']:
        # Use RPC against azure to validate the ARM template is well-formed
        verify_template_syntax(client, template_body_json=arm, template_parameters=template_params)

    if arguments['delete']:
        delete_cluster(client)

if __name__ == '__main__':
    run()
