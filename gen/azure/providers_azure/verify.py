#!/usr/bin/python

import json
import requests
import os


class AzureClient(object):
    API_VERSION = '2015-01-01'

    def __init__(self, subscription_id, tenant_id, client_id, client_secret):
        self._subscription_id = subscription_id
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret

        self._oauth_endpoint = 'https://login.microsoftonline.com/%s/oauth2/token' % (self._tenant_id)

    def get_token_from_client_credentials(self, endpoint, client_id, client_secret):
        payload = {'grant_type': 'client_credentials',
                   'client_id': client_id,
                   'client_secret': client_secret,
                   'resource': 'https://management.core.windows.net/',
                   }
        response = requests.post(endpoint, data=payload).json()
        return response['access_token']

    def get_auth_token(self):
        return self.get_token_from_client_credentials(
            endpoint=self._oauth_endpoint,
            client_id=self._client_id,
            client_secret=self._client_secret
            )

    def verify(self, template_body_json, template_parameters):
        resource_group_name = 'mj-2'
        deployment_name = 'verify_dummy'
        endpoint = 'https://management.azure.com/subscriptions/%s/resourcegroups/%s/providers/microsoft.resources/deployments/%s/validate' % (self._subscription_id, resource_group_name, deployment_name)
        params = {'api-version': AzureClient.API_VERSION}

        token = self.get_auth_token()
        headers = {'Authorization': 'Bearer %s' % (token)}

        template_json = self.get_template_json(template_body_json=template_body_json,
                                               template_parameters=template_parameters)
        r = requests.post(endpoint,
                          headers=headers,
                          params=params,
                          json=template_json)

        errors = r.json().get('error')
        if errors:
            raise Exception('Failed verification: %s' % errors)

        print(r.json())

    def get_template_json(self, template_body_json, template_parameters):
        return {"properties":
                {"template": template_body_json,
                 "mode": "Incremental",
                 "parameters": template_parameters
                 }
                }


if __name__ == "__main__":
    SUBSCRIPTION_ID = os.environ['AZURE_SUBSCRIPTION_ID']
    TENANT_ID = os.environ['AZURE_TENANT_ID']
    CLIENT_ID = os.environ['AZURE_CLIENT_ID']
    CLIENT_SECRET = os.environ['AZURE_CLIENT_SECRET']

    file_name = '/tmp/azure.json'
    template_body_json = json.load(open('/tmp/arm.json'))

    template_parameters = {
        "sshKeyData": {"value": "parametervalue1"},
        "authorizedSubnet": {"value": "10.0.0.0"},
        "region": {"value": "West US"},
        "numberOfMasters": {"value": 1},
        "numberOfPrivateSlaves": {"value": 5}
        }

    client = AzureClient(subscription_id=SUBSCRIPTION_ID,
                         tenant_id=TENANT_ID,
                         client_id=CLIENT_ID,
                         client_secret=CLIENT_SECRET)

    client.verify(template_body_json, template_parameters)
