entry = {
    'arguments': {
        "resolvers": "[\"168.63.129.16\"]",
        "ip_detect_filename": "scripts/ip-detect/azure.sh",
        'master_discovery': 'master_http_loadbalancer',
        'exhibitor_storage_backend': 'azure',
        'exhibitor_azure_prefix': "[[[variables('uniqueName')]]]",
        'exhibitor_azure_account_name': "[[[variables('storageAccountName')]]]",
        'exhibitor_azure_account_key': "[[[listKeys(resourceId('Microsoft.Storage/storageAccounts', variables('storageAccountName')), '2015-05-01-preview').key1]]]",  # noqa
        'exhibitor_address': "[[[reference('masterNodeNic0').ipConfigurations[0].properties.privateIPAddress]]]",
        'cluster_name': "[[[variables('uniqueName')]]]"
    }
}
