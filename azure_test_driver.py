#!/usr/bin/env python3

from functools import partial
import json
import os
import requests
import sys

from gen.azure.azure_client import (AzureClient,
                                    OutOfRetries,
                                    PollingFailureCondition,
                                    TemplateProvisioningState,
                                    AzureClientTemplateException,
                                    poll_until)


def verify_template_syntax(client, template_body_json, template_parameters):
    print("Verifying template ...")
    try:
        client.verify(template_body_json=template_body_json,
                      template_parameters=template_parameters)
    except AzureClientTemplateException as e:
        print("Template verification failed\n{}".format(e), file=sys.stderr)
        sys.exit(1)
    print("Template OK!")


def check_state(expected_state, response_json):
    provisioning_state = response_json.get('properties', {}).get('provisioningState')
    if provisioning_state == expected_state:
        return True
    print("Provisioning state: {}, Watching for: {}".format(
        provisioning_state, expected_state))
    return False


def poll_on_template_deploy_status(client):
    print("Polling on template deploy status ...")
    try:
        poll_until(tries=50,
                   initial_delay=30,
                   delay=15,
                   backoff=1,
                   success_lambda_list=[partial(check_state, TemplateProvisioningState.SUCCEEDED)],
                   failure_lambda_list=[partial(check_state, TemplateProvisioningState.FAILED)],
                   fn=client.get_template_deployment)
        print("Template deploy status OK")
    except (OutOfRetries, PollingFailureCondition) as e:
        print("Failed! {}".format(e), file=sys.stderr)
        print("Dumping template deployment ...", file=sys.stderr)
        json_pretty_print(client.get_template_deployment(), file=sys.stderr)
        print("Dumping template deployment operations ...", file=sys.stderr)
        json_pretty_print(client.list_template_deployment_operations(), file=sys.stderr)
        sys.exit(1)


def json_pretty_print(json_str, file=sys.stdout):
    print(json.dumps(json_str, sort_keys=True, indent=4, separators=(',', ':')), file=file)


def get_template_master_url(client):
    r = client.get_template_deployment()
    outputs = r.get('properties', {}).get('outputs', {})
    master_url = "http://{}".format(outputs.get('dnsAddress', {}).get('value'))
    return master_url


def get_dcos_ui(master_url):
    try:
        return requests.get(master_url)
    except requests.exceptions.ConnectionError:
        pass


def poll_on_dcos_ui_up(client):
    master_url = get_template_master_url(client)
    print("Master url: {}".format(master_url))

    try:
        poll_until(tries=90,
                   initial_delay=0,
                   delay=10,
                   backoff=1,
                   success_lambda_list=[
                       lambda r: r is not None and r.status_code == requests.codes.ok],
                   failure_lambda_list=[],
                   fn=lambda: get_dcos_ui(master_url))
        print("DCOS UI status OK")
    except (OutOfRetries, PollingFailureCondition) as e:
        # TODO(mj): dump information about the deployment here
        print(e, file=sys.stderr)

        sys.exit(1)


def clean_up_deploy(client):
    print("Canceling deployment ...")
    r = client.cancel_template_deployment()
    print(r)

    print("Deleting deployment ...")
    r = client.delete_template_deployment()
    print(r)

    print("Deleting resource group.")
    try:
        r = client.delete_resource_group()
        print(r)
    except ValueError:
        pass

    print("Polling on resource group status ...")
    try:
        poll_until(tries=180,
                   initial_delay=0,
                   delay=15,
                   backoff=1,
                   success_lambda_list=[partial(check_state, None)],
                   failure_lambda_list=[],
                   fn=client.get_resource_group)
    except OutOfRetries:
        print("Delete failed.", file=sys.stderr)
        sys.exit(1)

    print("Clean up successful.")


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
        "numberOfMasters": {"value": 1},
        "numberOfPrivateSlaves": {"value": 1},
        "numberOfPublicSlaves": {"value": 1}
        }

    # Output resource group
    print("Resource group name: {}".format(client._resource_group_name))
    print("Deployment name: {}".format(client._deployment_name))

    # Create a new resource group
    print("Creating new resource group")
    print(client.create_resource_group())

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

    # Poll on the template deploy status
    poll_on_template_deploy_status(client)

    # Poll on dcos ui
    poll_on_dcos_ui_up(client)

    # Clean up
    clean_up_deploy(client)


if __name__ == '__main__':
    run()
