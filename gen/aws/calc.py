defaults = {
  "resolvers": "[\"10.0.0.2\"]",
  "num_private_slaves": 5,
  "num_public_slaves": 1,
  "master_instance_type": "m3.xlarge",
  "fallback_dns": "10.0.0.2",
  "slave_instance_type": "m3.xlarge",
  "public_slave_instance_type": "m3.xlarge",
  "nat_instance_type": "m3.medium"
}

arguments = {
    'slave_cloud_config': '{{ slave_cloud_config }}',
    'master_cloud_config': '{{ master_cloud_config }}',
    'slave_public_cloud_config': '{{ slave_public_cloud_config }}'
}
