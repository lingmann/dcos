# wget and nogroup don't exist in the centos-7 image but are required,
# so we need to add them here.

require "json"

def render_installer(name, c)
  return <<-"EOF"
    source /etc/environment
    yum install -y wget docker
    echo nogroup:x:65500: >> /etc/group
    curl -L https://www.opscode.com/chef/install.sh | bash
    mkdir -p /var/chef/cookbooks/dcos
    tar -C /var/chef/cookbooks/dcos -xf "$(ls -t /vagrant/chef-*.tar.xz)"
    echo '{ "dcos": { "roles": [ #{ c[:roles].to_json } ]} }' > /tmp/node.json
    chef-solo -j /tmp/node.json -o 'recipe[dcos]'
  EOF
end
