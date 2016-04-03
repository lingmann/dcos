#!/usr/bin/env python3
"""Azure Image Creation, Management, Testing"""

import os
import random
import uuid
from urllib.parse import quote

import requests

OAUTH_ENDPOINT_TEMPLATE = 'https://login.microsoftonline.com/{}/oauth2/token'

MANAGEMENT_ROOT = 'https://management.azure.com'

SUBSCRIPTION_ENDPOINT = '{base_url}/subscriptions/{sub_id}'

RESOURCE_ENDPOINT = '{sub_url}/resourcegroups/{resource_grp}'

DEPLOYMENT_URI = '{res_grp_url}/providers/microsoft.resources/deployments/{deploy_name}'

RESOURCES = ('', 'cancel', 'validate', 'operations')


def setup_requests_session(token):
    session = requests.Session()
    session.params = {'api-version': AzureClient.API_VERSION}
    session.headers = {'Authorization': 'Bearer {}'.format(token)}

    return session


class AzureClientException(Exception):
    pass


class AzureClientTemplateException(AzureClientException):

    def __init__(self, template, errors):
        self.message = 'Template: {}\nFailed Verification: {}'.format(template,
                                                                      errors)
        self.template = template
        self.errors = errors
        super(AzureClientTemplateException, self).__init__(self.message)


class AzureClient(object):
    API_VERSION = '2015-01-01'

    @staticmethod
    def create_from_env_creds(**kwargs):
        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        tenant_id = os.environ.get('AZURE_TENANT_ID')
        client_id = os.environ.get('AZURE_CLIENT_ID')
        client_secret = os.environ.get('AZURE_CLIENT_SECRET')

        return AzureClient(subscription_id=subscription_id,
                           tenant_id=tenant_id,
                           client_id=client_id,
                           client_secret=client_secret,
                           **kwargs
                           )

    @staticmethod
    def create_from_existing(resource_group_name, deployment_name, **kwargs):
        subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        tenant_id = os.environ.get('AZURE_TENANT_ID')
        client_id = os.environ.get('AZURE_CLIENT_ID')
        client_secret = os.environ.get('AZURE_CLIENT_SECRET')

        return AzureClient(subscription_id=subscription_id,
                           tenant_id=tenant_id,
                           client_id=client_id,
                           client_secret=client_secret,
                           resource_group_name=resource_group_name,
                           deployment_name=deployment_name,
                           **kwargs
                           )

    def __init__(self, subscription_id, tenant_id, client_id, client_secret,
                 random_resource_group_name_prefix='testing', resource_group_name=None, deployment_name=None, **kwargs):
        self._subscription_id = subscription_id
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = None
        self._random_resource_group_name_prefix = random_resource_group_name_prefix

        if resource_group_name:
            self._resource_group_name = resource_group_name
        else:
            self._resource_group_name = self.get_random_resource_group_name()

        if deployment_name:
            self._deployment_name = deployment_name
        else:
            self._deployment_name = self.get_random_deployment_name()

        self._session = setup_requests_session(self.get_auth_token())
        self._url_space = self._generate_api_urls()

    # A url builder will be a nice thing to have
    @property
    def subscription_endpoint(self):
        return self._get_subscription_endpoint(self._subscription_id)

    def _get_subscription_endpoint(self, sub_id):
        return SUBSCRIPTION_ENDPOINT.format(
            base_url=MANAGEMENT_ROOT,
            sub_id=sub_id
        )

    @property
    def resource_endpoint(self):
        return self._get_resource_endpoint(
            self.subscription_endpoint,
            self._resource_group_name)

    def _get_resource_endpoint(self, sub_url, resource_group):
        return RESOURCE_ENDPOINT.format(
            sub_url=sub_url,
            resource_grp=resource_group
        )

    @property
    def deployment_endpoint(self):
        return DEPLOYMENT_URI.format(
            res_grp_url=self.resource_endpoint,
            deploy_name=self._deployment_name
        )

    def _generate_api_urls(self):
        '''
        Statically generate all the URI's this client will have to deal with

        @rtype: dict
        '''
        def url_format(u):
            return '{}/{}'.format(self.deployment_endpoint, u)
        urls = dict(zip(RESOURCES, map(url_format, RESOURCES)))
        print('INFO: url space is {}'.format(urls))

        return urls

    def get_token_from_client_credentials(self, endpoint, client_id, client_secret):
        payload = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'resource': 'https://management.core.windows.net/',
        }
        response = requests.post(endpoint, data=payload).json()
        return response['access_token']

    def get_auth_token(self):
        self._token = self._token or self.get_token_from_client_credentials(
            endpoint=OAUTH_ENDPOINT_TEMPLATE.format(self._tenant_id),
            client_id=self._client_id,
            client_secret=self._client_secret
            )
        return self._token

    def verify(self, template_body_json, template_parameters):
        endpoint = self._url_space['validate']

        template_json = self.get_template_json(template_body_json=template_body_json,
                                               template_parameters=template_parameters)

        r = self._session.post(endpoint, json=template_json)

        errors = r.json().get('error')
        if errors:
            # This could potentially spit out a really large template JSON!
            raise AzureClientTemplateException(template_json, errors)
        return r

    def get_template_deployment(self):
        return self._session.get(self._url_space['']).json()

    def get_template_deployment_status(self):
        template_deployment = self.get_template_deployment()
        return template_deployment.get('properties', {}).get('provisioningState')

    def create_template_deployment(self, template_body_json, template_parameters):
        template_json = self.get_template_json(template_body_json=template_body_json,
                                               template_parameters=template_parameters)
        r = self._session.put(self._url_space[''], json=template_json)
        return r.json()

    def cancel_template_deployment(self):
        endpoint = self._url_space['cancel']
        r = self._session.post(endpoint)

        return r  # or None?

    def delete_template_deployment(self):
        r = self._session.delete(self._url_space[''])

        return r  # or None?

    def get_template_json(self, template_body_json, template_parameters):
        return {
            "properties":
            {
                "template": template_body_json,
                "mode": "Incremental",
                "parameters": template_parameters
            }
        }

    def get_resource_group(self, resource_group_name=None):
        resource_group_name = resource_group_name or self._resource_group_name
        endpoint = self._get_resource_endpoint(self.subscription_endpoint, resource_group_name)

        return self._session.get(endpoint).json()

    def create_resource_group(self, location='East US', resource_group_name=None):
        resource_group_name = resource_group_name or self._resource_group_name

        endpoint = self._get_resource_endpoint(self.subscription_endpoint, resource_group_name)
        r = self._session.put(endpoint, json={'location': location})
        if r.ok:
            self._resource_group_name = resource_group_name
            # regenerate url space. ugly without a true model
            self._url_space = self._generate_api_urls()

        return r.json()

    def delete_resource_group(self, resource_group_name=None):
        resource_group_name = resource_group_name or self._resource_group_name

        # What happens if the resource group is deleted and then, some other action
        # like /cancel or /validate is executed?!
        # TODO: Add docs on proper Azure client usage and Exception(s) when client
        # is used incorrectly.

        endpoint = self._get_resource_endpoint(self.subscription_endpoint, resource_group_name)
        r = self._session.delete(endpoint)

        return r

    def status_delete_resource_group(self, poll_location):
        '''
        Return a Requests object indicating the status of a Resource Group
        delete operation when given a poll_location. The status will transition
        from 202 to 200 when the delete is complete.  See:
        https://msdn.microsoft.com/en-us/library/azure/dn790539.aspx
        '''
        r = self._session.get(poll_location)

        return r

    def get_random_resource_group_name(self):
        '''
        Generate a random group name no more than 18 characters long which
        consists of the first 8 characters of
        _random_resource_group_name_prefix and 10 random characters. The 18
        char limit protects us from exceeding ARM resource ID length
        limitations in various areas where this is used to construct a unique
        resource identifier.

        @rtype: str
        '''
        prefix = self._random_resource_group_name_prefix[:8]
        rand_string = ''.join(random.choice('01234567890abcdef') for n in range(10))
        return '{}{}'.format(prefix, rand_string)

    def get_random_deployment_name(self):
        return 'deployment{}'.format(uuid.uuid4().hex)

    def list_template_deployment_operations(self, provisioning_state_filter=None):
        # TODO(mj): add skiptoken parameter https://msdn.microsoft.com/en-us/library/azure/dn790518.aspx
        url = self._url_space['operations']
        if provisioning_state_filter:
            url += '?$filter=provisioningState eq \'' + quote(provisioning_state_filter) + '\''
        r = self._session.get(url)

        return r.json()


class TemplateProvisioningState(object):
    ACCEPTED = 'Accepted'
    READY = 'Ready'
    CANCELED = 'Canceled'
    FAILED = 'Failed'
    DELETED = 'Deleted'
    SUCCEEDED = 'Succeeded'
    RUNNING = 'Running'
    DELETING = 'Deleting'
