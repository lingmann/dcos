from functools import partial


def render_spot(name, arguments):
    spot_price = arguments.get(name + '_spot_price')
    if spot_price:
        return '"SpotPrice": "{}",'.format(spot_price)
    else:
        return ''

defaults = {
    "resolvers": "[\"10.0.0.2\"]",
    "num_private_slaves": 5,
    "num_public_slaves": 1,
    "master_instance_type": "m3.xlarge",
    "slave_instance_type": "m3.xlarge",
    "public_slave_instance_type": "m3.xlarge",
    "nat_instance_type": "m3.medium",
    "ip_detect_filename": "scripts/aws/ip-detector.sh",

    # If set to empty strings / unset then no spot instances will be used.
    "master_spot_price": "",
    "slave_spot_price": "",
    "slave_public_spot_price": ""
}

must = {
    'aws_master_spot_price': partial(render_spot, 'master'),
    'aws_slave_spot_price': partial(render_spot, 'slave'),
    'aws_slave_public_spot_price': partial(render_spot, 'slave_public')
}

arguments = {
    'master_cloud_config': '{{ master_cloud_config }}',
    'slave_cloud_config': '{{ slave_cloud_config }}',
    'slave_public_cloud_config': '{{ slave_public_cloud_config }}'
}

parameters = ['master_spot_price', 'slave_spot_price', 'slave_public_spot_price']
