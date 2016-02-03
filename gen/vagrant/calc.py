entry = {
    'default': {
        'ip_detect_filename': 'scripts/ip-detect/vagrant.sh',
        'resolvers': '["8.8.8.8", "8.8.4.4"]'
    },
    'must': {
        'cluster_name': 'Vagrant_SingleNode',
        'master_discovery': 'static',
        'exhibitor_storage_backend': 'shared_filesystem',
        'exhibitor_fs_config_dir': '/var/run/exhibitor',
        'master_list': '["127.0.0.1"]',
        'cluster_id': 'TODO-VAGRANT-SINGLENODE'
    }
}
