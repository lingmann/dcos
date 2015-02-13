Misc. thoughts

/opt/mesosphere/packages/{pkg-id}/package-contents

All packages are blobs, contain one file listing "required other packages"
	- Needed for config -> modules basic validation
	- Can leave out of v1

There are a couple of magical directories:
bin/
lib/
systemd/
config/

All magic direcotries must not contain conflicting things.
We symlink all the things into one directory.



Everything in systemd will get symlinked into
/etc/systemd/system/dcos.target.wants

Directory management:
All the directories do a rename current -> .old
.new -> current

Everything is done via directories.

/opt/mesosphere/current/{bin,lib,config}

We symlink items out of the /bin, /lib, etc. directories into the

one magic systemd unit: dcos.target which is symlinked on bootstrap into /etc/systemd/system/multi-user.target

Ever after then we'll manage
/etc/systemd/system/dcos.target.wants

So we can do all our symlink + rename magic.

All things are prepared in directories next to their installed directories to minimize
the odds of badness occurring.