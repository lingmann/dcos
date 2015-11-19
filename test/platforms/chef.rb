# docker and nogroup don't exist in the centos-7 image but are required,
# so we need to add them here.

require "json"

def render_installer(name, c)
  return <<-"EOF"
    source /etc/environment
    yum -y install docker unzip &&
    sed -i -e "s/OPTIONS='/OPTIONS='--insecure-registry 172.17.10.1:5000 /" /etc/sysconfig/docker &&
    systemctl enable docker &&
    systemctl start docker &&
    groupadd -g 65500 nogroup
    curl -fsSL https://www.opscode.com/chef/install.sh | bash
    mkdir -p /var/chef/cookbooks/dcos
    tar -C /var/chef/cookbooks/dcos -xf "$(ls -t /vagrant/chef-*.tar.xz|head -1)"
    echo '{ "dcos": { "roles": #{ c[:roles].to_json } } }' > /tmp/node.json
    cp /test_platforms/chef/chef-solo.service /etc/systemd/system
    systemctl --no-block start chef-solo
  EOF
end
