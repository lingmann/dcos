## Testing a DCOS image build with changes to pkgpanda, for the "Chef" path

### General Requirements

- Python3
- docker (1.5+ probably)
- Vagrant

### Prepare target test machine

- Follow instructions on http://vagrantbox.es and setup a VM (CentOS 7 for instance)
- Customize `Vagrantfile`
  - `vm.hostname = "test-chef"`
  - `config.vm.network "private_network", ip: "192.168.33.10"`
- `vagrant up` the newly created Vagrant VM
- `vagrant ssh`
- Install required packages
  - Docker : `wget -qO- https://get.docker.com/ | sh`
  - Chef client: `curl -L https://www.opscode.com/chef/install.sh | sudo bash`
- `service docker restart`
- Edit `/etc/hosts`, add `192.168.33.10 leader.mesos`

### Building dcos-image.

Setup a Python3 virtualenv containing pkgpanda, dcos-image dependencies.

```
# Make a virtualenv (python 3.4 method). Others work as well. Must be python3
WORKDIR=/tmp/work
pyvenv pkgpanda_env
source pkgpanda_env/bin/activate
git clone https://github.com/mesosphere/dcos-image.git $WORKDIR/dcos-image
git clone https://github.com/mesosphere/pkgpanda.git $WORKDIR/pkgpanda
cd $WORKDIR/pkgpanda
python3 setup.py develop

cd $WORKDIR/dcos-image
pip install -r requirements.txt
vi packages/pkgpanda/buildinfo.json # Edit ref and ref_origin to match pkgpanda branch
./chef.py
scp chef-*.tar.xz 192.168.33.10:/tmp
```

### Running `chef-solo` on test machine

Execute the following steps on the test machine

- `vagrant ssh` if not logged in to test machine
- Make directories needed for the `chef-solo` deploy
  - `mkdir -p /etc/mesosphere/roles`
- Create an `attributes.json` file 
```
cat > attributes.json <<EOF
{
  "run_list":[ "recipe[dcos]" ],
  "dcos":
  {
    "roles": ["master"]
  }
}
EOF
```
- `mkdir -p /var/chef/cookbooks`
- `knife cookbook create dcos`
- `tar zxvf /tmp/chef-*.tar.xz`
- `cp metadata.rb ~/.chef/cookbooks/dcos`
- `cp -R recipes ~/.chef/cookbooks/dcos`
- `sudo cp -R ~/.chef/cookbooks/dcos /var/chef/cookbooks`
- `sudo chef-solo -l debug -j attributes.json`
