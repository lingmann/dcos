SHELL        := /bin/bash
EMPTY        :=
SPACE        := $(EMPTY) $(EMPTY)
DOCKER_IMAGE := dcos-builder
UID          := $(shell id -u)
GID          := $(shell id -g)
PROJECT_ROOT := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
TAR          ?= gtar
ENVSUBST     ?= envsubst
SUDO         ?= sudo
DOCKER_RUN   ?= $(SUDO) docker run -v $(CURDIR):/dcos \
	-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
	-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)

PKG_VER      ?= 0.1.0

ifeq ($(origin PKG_REL), undefined)
REL_MAJOR    := 0
REL_MINOR    := 1
REL_PATCH    := $(shell date -u +'%Y%m%d%H%M%S')
SHA          := $(shell git rev-parse --short HEAD)
ITEMS        := $(REL_MAJOR) $(REL_MINOR) $(REL_PATCH) $(SHA)
PKG_REL      := $(subst $(SPACE),.,$(strip $(ITEMS)))
endif

ifeq ($(origin MESOS_GIT_SHA), undefined)
MESOS_GIT_SHA := $(shell cd ext/mesos 2>/dev/null && git rev-parse HEAD)
endif

ifeq ($(origin AWS_ACCESS_KEY_ID), undefined)
$(error environment variable AWS_ACCESS_KEY_ID must be set)
endif

ifeq ($(origin AWS_SECRET_ACCESS_KEY), undefined)
$(error environment variable AWS_SECRET_ACCESS_KEY must be set)
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
all: assemble

.PHONY: assemble
assemble: marathon zookeeper java mesos
	@# Extract PKG_VER and PKG_REL from the mesos manifest. Variables are global
	@# and as such are namespaced to the target ($@_) to prevent conflicts.
	$(eval $@_PKG_VER := \
		$(shell sed -rn 's/^DCOS_PKG_VER=(.*)/\1/p' ext/mesos.manifest))
	$(eval $@_PKG_REL := \
		$(shell sed -rn 's/^DCOS_PKG_REL=(.*)/\1/p' ext/mesos.manifest))
	@rm -rf dist && mkdir -p dist
	@# Add external components to DCOS tarball
	@cd ext && $(TAR) --numeric-owner --owner=0 --group=0 \
		-cf ../dist/dcos-$($@_PKG_VER)-$($@_PKG_REL).tar \
		marathon zookeeper java *.manifest
	@# Append Mesos build to DCOS tarball
	@cd build/mesos-toor/opt/mesosphere/dcos/$($@_PKG_VER)-$($@_PKG_REL) && \
		$(TAR) --numeric-owner --owner=0 --group=0 \
		-rf ../../../../../../dist/dcos-$($@_PKG_VER)-$($@_PKG_REL).tar *
	@# Compress
	@gzip dist/dcos-$($@_PKG_VER)-$($@_PKG_REL).tar
	@mv dist/dcos-$($@_PKG_VER)-$($@_PKG_REL).tar.gz \
		dist/dcos-$($@_PKG_VER)-$($@_PKG_REL).tgz
	@# Set up manifest contents
	@cat ext/*.manifest > dist/dcos-$($@_PKG_VER)-$($@_PKG_REL).manifest
	#@# Build bootstrap script
	@env "SUBST_PKG_VER=$($@_PKG_VER)" "SUBST_PKG_REL=$($@_PKG_REL)" \
		$(ENVSUBST) '$$SUBST_PKG_VER:$$SUBST_PKG_REL' \
		< src/scripts/bootstrap.sh \
		> dist/bootstrap.sh
	@# Checksum
	@cd dist && sha256sum dcos-$($@_PKG_VER)-$($@_PKG_REL).* > \
		dcos-$($@_PKG_VER)-$($@_PKG_REL).sha256

.PHONY: publish
publish: docker_image
	@# Extract DCOS_{PKG_VER,PKG_REL} from the mesos manifest. Variables are
	@# global and as such are namespaced to the target ($@_) to prevent conflicts.
	$(eval $@_PKG_VER := \
		$(shell sed -rn 's/^DCOS_PKG_VER=(.*)/\1/p' dist/dcos*.manifest))
	$(eval $@_PKG_REL := \
		$(shell sed -rn 's/^DCOS_PKG_REL=(.*)/\1/p' dist/dcos*.manifest))
	@# Use docker image as a convenient way to run AWS CLI tools
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/$($@_PKG_VER)-$($@_PKG_REL)/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 sync \
		/dcos/dist/ s3://downloads.mesosphere.io/dcos/$($@_PKG_VER)-$($@_PKG_REL)/ \
		--recursive
	@echo "Bootstrap URL's:"
	@echo "  Cloudfront: https://downloads.mesosphere.io/dcos/$($@_PKG_VER)-$($@_PKG_REL)/bootstrap.sh"
	@echo "  Direct: https://s3.amazonaws.com/downloads.mesosphere.io/dcos/$($@_PKG_VER)-$($@_PKG_REL)/bootstrap.sh"

.PHONY: publish-snapshot
publish-snapshot: publish
	@# Extract DCOS_{PKG_VER,PKG_REL} from the mesos manifest. Variables are
	@# global and as such are namespaced to the target ($@_) to prevent conflicts.
	$(eval $@_PKG_VER := \
		$(shell sed -rn 's/^DCOS_PKG_VER=(.*)/\1/p' dist/dcos*.manifest))
	$(eval $@_PKG_REL := \
		$(shell sed -rn 's/^DCOS_PKG_REL=(.*)/\1/p' dist/dcos*.manifest))
	@# Use docker image as a convenient way to run AWS CLI tools
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/snapshot/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/bootstrap.sh s3://downloads.mesosphere.io/dcos/snapshot/

.PHONY: mesos
mesos: docker_image ext/mesos ext/mesos.manifest

ext/mesos.manifest:
	$(DOCKER_RUN) \
		-e "PKG_VER=$(PKG_VER)" -e "PKG_REL=$(PKG_REL)" -e "MAKEFLAGS=$(MAKEFLAGS)" \
		$(DOCKER_IMAGE) bin/build_mesos.sh
	@# Chown files modified via Docker mount to UID/GID at time of make invocation
	$(SUDO) chown -R $(UID):$(GID) ext/mesos build
	@# Record state, used by other targets to determine DCOS version
	@echo 'DCOS_PKG_VER="$(PKG_VER)"' > $@
	@echo 'DCOS_PKG_REL="$(PKG_REL)"' >> $@
	@echo 'MESOS_GIT_SHA="$(MESOS_GIT_SHA)"' >> $@

debug: docker_image
	@# Extract DCOS_{PKG_VER,PKG_REL} from the mesos manifest. Variables are
	@# global and as such are namespaced to the target ($@_) to prevent conflicts.
	$(eval $@_PKG_VER := \
		$(shell sed -rn 's/^DCOS_PKG_VER=(.*)/\1/p' dist/dcos*.manifest))
	$(eval $@_PKG_REL := \
		$(shell sed -rn 's/^DCOS_PKG_REL=(.*)/\1/p' dist/dcos*.manifest))
	$(DOCKER_RUN) \
		-i -t -e "PKG_VER=$($@_PKG_VER)" -e "PKG_REL=$($@_PKG_REL)" -e "MAKEFLAGS=$(MAKEFLAGS)" \
		$(DOCKER_IMAGE) bash

.PHONY: docker_image
docker_image:
	$(SUDO) docker build -t "$(DOCKER_IMAGE)" .

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
	$(SUDO) rm -rf build

.PHONY: distclean
distclean: clean
	$(SUDO) rm -rf dist ext/*
	$(SUDO) docker rmi -f $(DOCKER_IMAGE) 2>/dev/null || true

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
