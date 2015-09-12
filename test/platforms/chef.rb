# docker and nogroup don't exist in the centos-7 image but are required,
# so we need to add them here.

require "json"

def render_installer(name, c)
  return <<-"EOF"
    source /etc/environment
    yum install -y docker
    echo nogroup:x:65500: >> /etc/group
    curl -L https://www.opscode.com/chef/install.sh | bash
    mkdir -p /var/chef/cookbooks/dcos
    tar -C /var/chef/cookbooks/dcos -xf "$(ls -t /vagrant/chef-*.tar.xz|head -1)"
    echo '{ "dcos": { "roles": #{ c[:roles].to_json } } }' > /tmp/node.json
    cp /vagrant/test/platforms/chef/chef-solo.service /etc/systemd/system
    systemctl --no-block start chef-solo
  EOF
end
