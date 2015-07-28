def validate(arguments):
    assert not arguments['exhibitor_zk_hosts'].startswith('zk://') and "Must be of the form `host:port,host:port`"
    assert arguments['exhibitor_zk_path'].startswith('/') and "Must be of the form /path/to/znode"
