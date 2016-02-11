#!/usr/bin/env python3

import json
import os
import requests
import sys
import traceback

from gen.azure.azure_client import (AzureClient,
                                    AzureClientException,
                                    TemplateProvisioningState,
                                    AzureClientTemplateException)
from retrying import retry


def verify_template_syntax(client, template_body_json, template_parameters):
    print("Verifying template ...")
    try:
        client.verify(template_body_json=template_body_json,
                      template_parameters=template_parameters)
    except AzureClientTemplateException as e:
        print("Template verification failed\n{}".format(e), file=sys.stderr)
        sys.exit(1)
    print("Template OK!")


def json_pretty_print(json_str, file=sys.stdout):
    print(json.dumps(json_str, sort_keys=True, indent=4, separators=(',', ':')), file=file)


def get_template_output_value(client, output_key):
    '''
    Returns the ARM deployment output value for the given output_key.
    Raises an AzureClientException if the key is not found.
    '''
    r = client.get_template_deployment()
    outputs = r.get('properties', {}).get('outputs', {})
    if output_key not in outputs:
        raise AzureClientException("output_key: {} does not exist in deployment".format(output_key))
    return outputs.get(output_key).get('value')


def get_dcos_ui(master_url):
    try:
        return requests.get(master_url)
    except requests.exceptions.ConnectionError:
        pass


def run():
    template_path = os.environ['AZURE_TEMPLATE_PATH']

    arm = open(template_path).read()

    client = AzureClient.create_from_env_creds(
        random_resource_group_name_prefix='teamcity')

    # sshKeyData is the public SSH key used as the authorized key for the default cluster user (core)
    # Set to the public SSH key for mesosphere-demo: https://mesosphere.onelogin.com/notes/18444
    dummy_template_parameters = {
        "sshKeyData": {"value": (
            "MIIDXTCCAkWgAwIBAgIJAIIFgegSdSRMMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHw"
            "YDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcNMTUwNDA4MjA0MDQ5WhcNMTYwNDA3MjA0MDQ5WjBFMQswCQYDVQQGEwJBVTET"
            "MBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMI"
            "IBCgKCAQEAhx70Yc7zSzrqz3OyfoB8S22zmZ4+jpO+Dir70Qx4p8wtfhcsLjoPaNmArww6WJdbSUJktDsgpzmJVKS8fAoRnt0XtWmVETiy"
            "wGKOMCldFYqdwLjdaWJZ4qqGDs5upMVCcV7cnCf7TBnkBNv3Az5SyzgBk00zUjcaEiwixPt9vyb4KOpI/WdXnVAI/nULdv/6DAdWLcCtGu"
            "dyw9HEc889Ry2PHWF/6U39WWKG10ln5qYNO2Nf1OBsgI1D5kZlDj5ALnSbJ4dtH7KG1C/Zg1bOumZ4rLDYICpnODLK3/KqMWdqjcNxC8gQ"
            "o5vd0kV1BUsYU6kDJYXvxvNd8ICjMYIycwIDAQABo1AwTjAdBgNVHQ4EFgQU4bayYwTyhuM0RxKHXiQWiLyY/0MwHwYDVR0jBBgwFoAU4b"
            "ayYwTyhuM0RxKHXiQWiLyY/0MwDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAKQppNEpZbjd875EYiw5gPvk3hFceHoDL1+ni"
            "ZZ/HWxkn/f5gZ8rJLrGRnxXMiD8jXtNmjHSHePR2vdeNQ2N17ObasrmFynI4LiqOOmaA5VfOWAA7AvpmJTL8hyB4xK96bYtlBVUQ9iJf+g"
            "fwy1fzR8X8pEOaLhXkUTZb7Oex97H81yrau15PI1OGjDrQQtMpWU8tGVfXECh07/Rg1ODnza9ddY+x0xLBFjfyTY7PrIwcdhNCP82QKSfH"
            "DltDbssw4wIm+NPsnZ9NodtjgAFxC8HEDFTozYueHOTi4DzgRjGfTHjkhwZd/LPAYXNb8PxB82cermpqn4tn0nOT76fPGg==")},
        "authorizedSubnet": {"value": "0.0.0.0/0"},
        "numberOfPrivateSlaves": {"value": 1},
        "numberOfPublicSlaves": {"value": 1}
        }

    # Output resource group
    print("Resource group name: {}".format(client._resource_group_name))
    print("Deployment name: {}".format(client._deployment_name))

    # Create a new resource group
    print("Creating new resource group")
    print(client.create_resource_group())

    test_successful = False

    try:
        # Use RPC against azure to validate the ARM template is well-formed
        verify_template_syntax(client,
                               template_body_json=json.loads(arm),
                               template_parameters=dummy_template_parameters)

        # Actually create a template deployment
        print("Creating template deployment ...")
        deployment_response = client.create_template_deployment(
            template_body_json=json.loads(arm),
            template_parameters=dummy_template_parameters)
        json_pretty_print(deployment_response)

        @retry(wait_fixed=(5*1000), stop_max_delay=(15*60*1000))
        def poll_on_template_deploy_status(client):
            provisioning_state = client.get_template_deployment().get('properties', {}).get('provisioningState')
            assert provisioning_state == TemplateProvisioningState.SUCCEEDED, \
                "Template did not finish deploying in time, provisioning state: {}".format(provisioning_state)

        print("Waiting for template to deploy ...")
        poll_on_template_deploy_status(client)

        master_lb = get_template_output_value(client, 'dnsAddress')
        master_url = "http://{}".format(master_lb)

        print("Template deployed using SSH private key: https://mesosphere.onelogin.com/notes/18444")
        print("For troubleshooting, master0 can be reached using: ssh -p 2200 core@{}".format(master_lb))

        @retry(wait_fixed=(5*1000), stop_max_delay=(15*60*1000))
        def poll_on_dcos_ui_up(master_url):
            r = get_dcos_ui(master_url)
            assert r is not None and r.status_code == requests.codes.ok, \
                "Unable to reach DCOS UI: {}".format(master_url)

        print("Waiting for DCOS UI at: {} ...".format(master_url))
        poll_on_dcos_ui_up(master_url)
        test_successful = True

    except (AssertionError, AzureClientException) as ex:
        print("ERROR: {}".format(ex), file=sys.stderr)
        traceback.print_tb(ex.__traceback__)

    finally:
        @retry(wait_exponential_multiplier=1000, wait_exponential_max=60*1000, stop_max_delay=(30*60*1000))
        def delete_resource_group(client):
            print("Deleting resource group: {} ...".format(client._resource_group_name))
            del_response = client.delete_resource_group()
            assert del_response.status_code == requests.codes.accepted, \
                "Delete request failed: {}".format(del_response.status_code)
            return del_response.headers['Location']

        poll_location = delete_resource_group(client)

        @retry(wait_fixed=(5*1000), stop_max_delay=(15*60*1000))
        def wait_for_delete(poll_location):
            r = client.status_delete_resource_group(poll_location)
            assert r.status_code == requests.codes.ok, "Timed out waiting for delete: {}".format(r.status_code)

        print("Waiting for delete ...")
        wait_for_delete(poll_location)

        print("Clean up successful")

    if test_successful:
        print("Azure test deployment succeeded")
    else:
        print("ERROR: Azure test deployment failed", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    run()
