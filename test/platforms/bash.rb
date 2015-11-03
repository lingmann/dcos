def render_installer(name, c)
  # docker and nogroup don't exist in the centos-7 image but are required,
  # so we need to add them here
  return <<-"EOF"
    yum -y install docker unzip &&
    systemctl enable docker &&
    systemctl start docker &&
    groupadd -g 65500 nogroup &&
    cp /test_platforms/bash/install-oneshot.service /etc/systemd/system
    echo #{ c[:roles].join(" ") } > /setup_roles
    systemctl --no-block start install-oneshot
    bash
  EOF
end
