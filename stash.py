# Stashed bits for later


def remove_service(cloud_config, name):
    # Keep track of pre + post length to track if we removed one service and only
    # one service.
    service_count = len(cloud_config['coreos']['units'])
    cloud_config['coreos']['units'] = filter(
            lambda service: service.name != name,
            cloud_config['coreos']['units'])

    new_service_count = len(cloud_config['coreos']['units'])
    # Check to see that we found and removed exactly one service
    assert new_service_count == service_count - 1

    return cloud_config


def change_file_content(cloud_config, name, new_content, mode=0o644):
    file_count = len(cloud_config['write_files'])
    # Remove old
    cloud_config['write_files'] = filter(
        lambda file: file.name == name)
    new_file_count = len(cloud_config['write_files'])
    # Validate that we found and removed exactly one service
    assert new_file_count == file_count - 1

    # Add the new file
    cloud_config['write_files'].append({
        'name': name,
        'content': new_content,
        'permissions': mode
        })


download_local_mount = """[Unit]
Description=Download the DCOS
ConditionPathExists=!/opt/mesosphere/
[Service]
EnvironmentFile=/etc/mesosphere/setup-flags/bootstrap-id
Type=oneshot
ExecStart=/usr/bin/tar -axf /shared/packages/${BOOTSTRAP_ID}.bootstrap.tar.xz -C /opt/mesosphere
"""
