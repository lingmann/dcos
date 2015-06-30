defaults = {
  "resolvers": ["10.0.0.2"]
}

arguments = {
    'start_param': '{ "Fn::FindInMap" : [ "Parameters", "',
    'end_param': '", "default" ] }',
    'slave_cloud_config': '{{ slave_cloud_config }}',
    'master_cloud_config': '{{ master_cloud_config }}',
    'public_slave_cloud_config': '{{ public_slave_cloud_config }}'
}
