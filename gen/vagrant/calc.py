entry = {
    'arguments': {
        "cluster_name": "Vagrant_SingleNode",
        "master_discovery": "static"
    },
    'defaults': {
        "ip_detect_filename": "scripts/ip-detect/vagrant.sh",
        "resolvers": "[\"8.8.8.8\", \"8.8.4.4\"]"
    },
    'must': {
        'exhibitor_storage_backend': lambda: 'shared_filesystem',
        'exhibitor_fs_config_dir': lambda: '/var/run/exhibitor',
        'master_list': lambda: '["127.0.0.1"]'
    }
}
