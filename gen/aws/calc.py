def get_spot_str(name, spot_price):
    if spot_price:
        return '"SpotPrice": "{}",'.format(spot_price)
    else:
        return ''

defaults = {
    "resolvers": "[\"10.0.0.2\"]",
    "num_private_slaves": "5",
    "num_public_slaves": "1",
    "master_instance_type": "m3.xlarge",
    "slave_instance_type": "m3.xlarge",
    "public_slave_instance_type": "m3.xlarge",
    "nat_instance_type": "m3.medium",
    "ip_detect_filename": "scripts/ip-detect/aws.sh",

    # If set to empty strings / unset then no spot instances will be used.
    "master_spot_price": "",
    "slave_spot_price": "",
    "slave_public_spot_price": ""
}

must = {
    'aws_master_spot_price': lambda master_spot_price: get_spot_str('master', master_spot_price),
    'aws_slave_spot_price': lambda slave_spot_price: get_spot_str('slave', slave_spot_price),
    'aws_slave_public_spot_price': lambda slave_public_spot_price: get_spot_str('slave_public', slave_public_spot_price)
}

arguments = {
    'master_cloud_config': '{{ master_cloud_config }}',
    'slave_cloud_config': '{{ slave_cloud_config }}',
    'slave_public_cloud_config': '{{ slave_public_cloud_config }}'
}

parameters = ['master_spot_price', 'slave_spot_price', 'slave_public_spot_price']
