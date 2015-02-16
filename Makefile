SHELL        := /bin/bash
EMPTY        :=
SPACE        := $(EMPTY) $(EMPTY)
DOCKER_IMAGE := dcos-builder
UID          := $(shell id -u)
GID          := $(shell id -g)
PROJECT_ROOT := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
TAR          ?= gtar

PKG_VER      ?= 0.0.1

ifeq ($(origin PKG_REL), undefined)
	REL_MAJOR  := 0
	REL_MINOR  := 1
	REL_PATCH  := $(shell date -u +'%Y%m%d%H%M%S')
	SHA        := $(shell git rev-parse --short HEAD)
	ITEMS      := $(REL_MAJOR) $(REL_MINOR) $(REL_PATCH) $(SHA)
	PKG_REL    := $(subst $(SPACE),.,$(strip $(ITEMS)))
endif

.PHONY: help
help:
	@echo "Build the DCOS tarball (requires Docker with volume mount support)"
	@echo ""
	@echo "Examples:"
	@echo "  Snapshot build:"
	@echo "    make all"
	@echo "  Parallel snapshot build (12 jobs):"
	@echo "    make MAKEFLAGS=-j12 all"
	@echo ""
	@echo "Configurable options via environment variable and defaults"
	@echo "  PKG_VER: $(PKG_VER)"
	@echo "  PKG_REL: $(PKG_REL)"
	@echo "  MAKEFLAGS: $(MAKEFLAGS)"
	@exit 0

.PHONY: all
all: tarball

.PHONY: mesos
mesos: docker_image ext/mesos ext/mesos.manifest

ext/mesos.manifest:
	sudo docker run \
		-e "PKG_VER=$(PKG_VER)" -e "PKG_REL=$(PKG_REL)" -e "MAKEFLAGS=$(MAKEFLAGS)" \
		-v $(CURDIR):/dcos $(DOCKER_IMAGE) bin/build_mesos.sh
	@# Chown files modified via Docker mount to UID/GID at time of make invocation
	sudo chown -R $(UID):$(GID) ext/mesos build
	@# Record state, used by other targets to determine DCOS version
	@echo 'DCOS_PKG_VER="$(PKG_VER)"' > $@
	@echo 'DCOS_PKG_REL="$(PKG_REL)"' >> $@

.PHONY: docker_image
docker_image:
	sudo docker build -t "$(DOCKER_IMAGE)" .

.PHONY: tarball
tarball: mesos
	mkdir -p dist
	cd build/mesos-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL) && \
		tar --numeric-owner --owner=0 --group=0 -cz \
		-f ../../../../../../dist/dcos-$(PKG_VER)-$(PKG_REL).tgz mesos

ext/mesos:
	@echo "ERROR: mesos checkout required at the desired build version"
	@echo "Please check out at the desired build version. For example:"
	@echo "  git clone https://git-wip-us.apache.org/repos/asf/mesos.git ext/mesos"
	@echo "  pushd ext/mesos && git checkout 0.21.1 && popd"
	@exit 1

.PHONY: marathon
marathon: ext/marathon/marathon.jar

ext/marathon/marathon.jar:
	@echo "Downloading Marathon from $(MARATHON_URL)"
	@# Transform paths in tarball so that marathon jar is extracted to desired
	@# location. The wildcard pattern specified is pre-transform.
	@wget -qO- "$(MARATHON_URL)" | \
		$(TAR) -xzf - --transform 's,marathon-[0-9.]+/target/scala-[0-9.]+/marathon-assembly-[0-9.]+\.jar,marathon/marathon.jar,x' \
		--show-transformed -C ext/ --wildcards '*/marathon-assembly-*.jar'
	@echo 'MARATHON_URL="$(MARATHON_URL)"' > ext/marathon.manifest
	@test -f $@

.PHONY: zookeeper
zookeeper: ext/zookeeper/bin/zkServer.sh

ext/zookeeper/bin/zkServer.sh:
	@echo "Downloading Zookeeper from $(ZOOKEEPER_URL)"
	@wget -qO- "$(ZOOKEEPER_URL)" | \
		$(TAR) -xzf - --transform 's,^zookeeper-[0-9.]+,zookeeper,x' \
		--show-transformed -C ext/
	@echo 'ZOOKEEPER_URL="$(ZOOKEEPER_URL)"' > ext/zookeeper.manifest
	@test -f $@

.PHONY: java
java: ext/java/bin/java

ext/java/bin/java:
	@echo "Downloading Java from $(JAVA_URL)"
	@wget -qO- "$(JAVA_URL)" | \
		$(TAR) -xzf - --transform 's,^jre[0-9._]+,java,x' \
		--show-transformed -C ext/
	@echo 'JAVA_URL="$(JAVA_URL)"' > ext/java.manifest
	@test -f $@

.PHONY: clean
clean:
	sudo rm -rf build

.PHONY: dist-clean
dist-clean: clean
	sudo rm -rf dist ext/*
	sudo docker rmi -f $(DOCKER_IMAGE) 2>/dev/null || true

###############################################################################
# Targets to test for pre-requisites
###############################################################################

.PHONY: prereqs
prereqs: gtar docker sha256sum sed

.PHONY: gtar
gtar:
	@hash $(TAR) 2>/dev/null || { echo >&2 "ERROR: GNU tar required for --transform"; exit 1; }

.PHONY: docker
docker:
	@hash docker 2>/dev/null || { echo >&2 "ERROR: docker required"; exit 1; }

.PHONY: sha256sum
sha256sum:
	@hash sha256sum 2>/dev/null || { echo >&2 "ERROR: sha256sum required"; exit 1; }

.PHONY: sed
sed:
	@hash sed 2>/dev/null || { echo >&2 "ERROR: sed required"; exit 1; }
