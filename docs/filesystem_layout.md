```
/etc/mesosphere/dcos-bootstrap/role/{master,slave}
/etc/systemd/dcos.target.wants/
	mesos-master.service
/opt/mesosphere/
	bin/
	lib/
	etc/
	environment
	active/
		mesos -> /opt/mesosphere/packages/mesos-0.22.0
		java -> ...
		zookeeper -> ...
	packages/
		mesos-config/
			etc/
		mesos-0.22.0/
			bin/
			lib/
			libexec/
			...
			systemd/
				mesos-master.service
		java-ranodmversionstring/
			...
		zookeeper-0.123/
			...
```