$num_master_instances = 3
$num_slave_instances = 2
$network = "172.17.10"
$box = "centos/7"

def render_installer(name, c)
  return "echo 'No platform specified'; exit 1"
end
