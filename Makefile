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
ANNOTATE     ?= $(PROJECT_ROOT)/bin/annotate.sh
DOCKER_RUN   ?= $(SUDO) docker run -v $(CURDIR):/dcos \
	-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
	-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)

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
	@echo "    make set-version"
	@echo "    make all"
	@echo "  Parallel build (12 jobs) and non-snapshot version:"
	@echo "    make PKG_VER=0.2.0 PKG_REL=1.0 set-version"
	@echo "    make MAKEFLAGS=-j12 all"
	@echo ""
	@echo "Configurable options via environment variable and defaults"
	@echo "  MAKEFLAGS: $(MAKEFLAGS)"
	@exit 0

ifeq ($(wildcard build/dcos.manifest),)
$(warning Please set version with 'set-version' target.)
endif

PKG_VER := $(shell sed -rn 's/^DCOS_PKG_VER=(.*)/\1/p' build/dcos.manifest)
PKG_REL := $(shell sed -rn 's/^DCOS_PKG_REL=(.*)/\1/p' build/dcos.manifest)

.PHONY: set-version
set-version:
	@echo "Setting PKG_VER and PKG_REL in build/dcos.manifest"
	@mkdir -p build
	@rm -f build/dcos.manifest
	@if [[ "$(PKG_VER)" == "" ]]; then echo "DCOS_PKG_VER=0.1.0" >> build/dcos.manifest; else echo "DCOS_PKG_VER=$(PKG_VER)" >> build/dcos.manifest; fi
	@if [[ "$(PKG_REL)" == "" ]]; then echo "DCOS_PKG_REL=0.1.$$(date -u +'%Y%m%d%H%M%S')" >> build/dcos.manifest; else echo "DCOS_PKG_REL=$(PKG_REL)" >> build/dcos.manifest; fi
	@cat build/dcos.manifest

build/dcos.manifest:
	@echo "ERROR: build/dcos.manifest must be created first"
	@echo ""
	@echo "Examples:"
	@echo " For a snapshot version:"
	@echo "  make set-version"
	@echo " For a fixed version:"
	@echo "  make PKG_VER=0.1.0 PKG_REL=0.1.20150225224014 set-version"
	@exit 1

.PHONY: all
all: assemble

.PHONY: assemble
assemble: marathon zookeeper java mesos python
	@rm -rf dist && mkdir -p dist
	@# Append external components to DCOS tarball
	@cd ext && $(TAR) --numeric-owner --owner=0 --group=0 \
		-rf ../dist/dcos-$(PKG_VER)-$(PKG_REL).tar \
		marathon zookeeper java
	@# Append build manifests to DCOS tarball
	@cd build && $(TAR) --numeric-owner --owner=0 --group=0 \
		-rf ../dist/dcos-$(PKG_VER)-$(PKG_REL).tar \
		*.manifest
	@# Append Mesos build to DCOS tarball
	@cd build/mesos-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL) && \
		$(TAR) --numeric-owner --owner=0 --group=0 \
		-rf ../../../../../../dist/dcos-$(PKG_VER)-$(PKG_REL).tar *
	@# Append Python build to DCOS tarball
	@cd build/python-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL) && \
		$(TAR) --numeric-owner --owner=0 --group=0 \
		-rf ../../../../../../dist/dcos-$(PKG_VER)-$(PKG_REL).tar *
	@# Compress
	@gzip dist/dcos-$(PKG_VER)-$(PKG_REL).tar
	@mv dist/dcos-$(PKG_VER)-$(PKG_REL).tar.gz \
		dist/dcos-$(PKG_VER)-$(PKG_REL).tgz
	@# Set up manifest contents
	@cat build/*.manifest > dist/dcos-$(PKG_VER)-$(PKG_REL).manifest
	#@# Build bootstrap script
	@env "SUBST_PKG_VER=$(PKG_VER)" "SUBST_PKG_REL=$(PKG_REL)" \
		$(ENVSUBST) '$$SUBST_PKG_VER:$$SUBST_PKG_REL' \
		< src/scripts/bootstrap.sh \
		> dist/bootstrap.sh
	@# Checksum
	@cd dist && sha256sum dcos-$(PKG_VER)-$(PKG_REL).* > \
		dcos-$(PKG_VER)-$(PKG_REL).sha256

.PHONY: publish
publish: docker_image
	@# Use docker image as a convenient way to run AWS CLI tools
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/ s3://downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/ \
		--recursive
	@echo "Bootstrap URL's:"
	@echo "  Cloudfront: https://downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/bootstrap.sh"
	@echo "  Direct: https://s3.amazonaws.com/downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/bootstrap.sh"

.PHONY: publish-snapshot
publish-snapshot: publish
	@# Use docker image as a convenient way to run AWS CLI tools
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/snapshot/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/bootstrap.sh s3://downloads.mesosphere.io/dcos/snapshot/

debug: docker_image
	$(DOCKER_RUN) \
		-i -t -e "PKG_VER=$(PKG_VER)" -e "PKG_REL=$(PKG_REL)" -e "MAKEFLAGS=$(MAKEFLAGS)" \
		$(DOCKER_IMAGE) bash

.PHONY: docker_image
docker_image:
	$(ANNOTATE) $(SUDO) docker build -t "$(DOCKER_IMAGE)" . \
		&> build/docker_image.log
	>&2 egrep '^stderr: ' build/docker_image.log || true
	@echo "docker_image build complete"

ext/mesos:
	@echo "ERROR: mesos checkout required at the desired build version"
	@echo "Please check out at the desired build version. For example:"
	@echo "  git clone https://git-wip-us.apache.org/repos/asf/mesos.git ext/mesos"
	@echo "  pushd ext/mesos && git checkout 0.21.1 && popd"
	@exit 1

.PHONY: mesos
mesos: build/mesos.manifest docker_image ext/mesos
build/mesos.manifest:
	$(ANNOTATE) $(DOCKER_RUN) \
		-e "PKG_VER=$(PKG_VER)" -e "PKG_REL=$(PKG_REL)" -e "MAKEFLAGS=$(MAKEFLAGS)" \
		$(DOCKER_IMAGE) bin/build_mesos.sh &> build/mesos.log
	>&2 egrep '^stderr: ' build/mesos.log || true
	@echo "mesos build complete"
	@# Chown files modified via Docker mount to UID/GID at time of make invocation
	$(SUDO) chown -R $(UID):$(GID) ext/mesos build
	@# Record Mesos stuff to manifest
	@echo 'MESOS_GIT_SHA=$(MESOS_GIT_SHA)' > $@

.PHONY: python
python: build/python.manifest
build/python.manifest:
	@if [[ "$(PYTHON_URL)" == "" ]]; then echo "PYTHON_URL is unset"; exit 1; fi
	@echo "Downloading Python from $(PYTHON_URL)"
	@wget -qO- "$(PYTHON_URL)" | \
		$(TAR) -xzf - --transform 's,Python-[0-9.]+,python,x' \
		--show-transformed -C ext/
	$(ANNOTATE) $(DOCKER_RUN) \
		-e "PKG_VER=$(PKG_VER)" -e "PKG_REL=$(PKG_REL)" -e "MAKEFLAGS=$(MAKEFLAGS)" \
		$(DOCKER_IMAGE) bin/build_python.sh &> build/python.log
	>&2 egrep '^stderr: ' build/python.log || true
	@echo "python build complete"

	@# Chown files modified via Docker mount to UID/GID at time of make invocation
	$(SUDO) chown -R $(UID):$(GID) ext/python build
	@echo 'PYTHON_URL=$(PYTHON_URL)' > $@

.PHONY: marathon
marathon: build/marathon.manifest
build/marathon.manifest:
	@echo "Downloading Marathon from $(MARATHON_URL)"
	@if [[ "$(MARATHON_URL)" == "" ]]; then echo "MARATHON_URL is unset"; exit 1; fi
	@# Transform paths in tarball so that marathon jar is extracted to desired
	@# location. The wildcard pattern specified is pre-transform.
	@wget -qO- "$(MARATHON_URL)" | \
		$(TAR) -xzf - --transform 's,marathon-[0-9.]+/target/scala-[0-9.]+/marathon-assembly-[0-9.]+\.jar,marathon/marathon.jar,x' \
		--show-transformed -C ext/ --wildcards '*/marathon-assembly-*.jar'
	@echo 'MARATHON_URL=$(MARATHON_URL)' > $@

.PHONY: zookeeper
zookeeper: build/zookeeper.manifest
build/zookeeper.manifest:
	@echo "Downloading Zookeeper from $(ZOOKEEPER_URL)"
	@if [[ "$(ZOOKEEPER_URL)" == "" ]]; then echo "ZOOKEEPER_URL is unset"; exit 1; fi
	@wget -qO- "$(ZOOKEEPER_URL)" | \
		$(TAR) -xzf - --transform 's,^zookeeper-[0-9.]+,zookeeper,x' \
		--show-transformed -C ext/
	@echo 'ZOOKEEPER_URL=$(ZOOKEEPER_URL)' > $@

.PHONY: java
java: build/java.manifest
build/java.manifest:
	@echo "Downloading Java from $(JAVA_URL)"
	@if [[ "$(JAVA_URL)" == "" ]]; then echo "JAVA_URL is unset"; exit 1; fi
	@wget -qO- "$(JAVA_URL)" | \
		$(TAR) -xzf - --transform 's,^jre[0-9._]+,java,x' \
		--show-transformed -C ext/
	@echo 'JAVA_URL=$(JAVA_URL)' > $@

.PHONY: clean
clean:
	$(SUDO) rm -rf build dist

.PHONY: distclean
distclean: clean
	$(SUDO) rm -rf ext/*
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
