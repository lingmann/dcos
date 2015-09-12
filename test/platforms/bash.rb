def render_installer(name, c)
  # docker and nogroup don't exist in the centos-7 image but are required,
  # so we need to add them here
  return <<-"EOF"
    yum install -y docker &&
    echo nogroup:x:65500: >> /etc/group &&
    bash /vagrant/dcos_install.sh #{ c[:roles].join(" ") }
  EOF
end
