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
JQ					 ?= jq
ANNOTATE     ?= $(PROJECT_ROOT)/bin/annotate.sh
DOCKER_RUN   ?= $(SUDO) docker run -v $(CURDIR):/dcos \
	-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
	-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)

ifeq ($(origin MESOS_GIT_SHA), undefined)
MESOS_GIT_SHA := $(shell cd ext/mesos 2>/dev/null && git rev-parse HEAD)
endif

ifeq ($(origin MESOS_GIT_URL), undefined)
MESOS_GIT_URL := $(PROJECT_ROOT)/ext/mesos
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
assemble: build/marathon.manifest build/zookeeper.manifest build/java.manifest
assemble: build/mesos.manifest build/python.manifest
	@rm -rf dist && mkdir -p dist
	@cp build/*/*.tar.xz dist
	@# TODO: Change pkgpanda strap so our work dir is not /opt/mesosphere
	@$(SUDO) rm -rf /opt/mesosphere
	@cd dist && $(SUDO) pkgpandastrap tarball --role=slave / *.tar.xz
	@# Set up manifest contents
	@cat build/*.manifest > dist/dcos-$(PKG_VER)-$(PKG_REL).manifest
	#@# Build bootstrap script
	@env "SUBST_PKG_VER=$(PKG_VER)" "SUBST_PKG_REL=$(PKG_REL)" \
		$(ENVSUBST) '$$SUBST_PKG_VER:$$SUBST_PKG_REL' \
		< src/scripts/bootstrap.sh \
		> dist/bootstrap.sh
	@# Checksum
	@cd dist && sha256sum *.tar.xz *.manifest *.sh > \
		dcos-$(PKG_VER)-$(PKG_REL).sha256

.PHONY: publish
publish: build/docker_image
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
publish-snapshot: publish build/docker_image
	@# Use docker image as a convenient way to run AWS CLI tools
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/snapshot/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/bootstrap.sh s3://downloads.mesosphere.io/dcos/snapshot/

debug: build/docker_image
	$(DOCKER_RUN) \
		-i -t -e "PKG_VER=$(PKG_VER)" -e "PKG_REL=$(PKG_REL)" -e "MAKEFLAGS=$(MAKEFLAGS)" \
		$(DOCKER_IMAGE) bash

.PHONY: docker_image
docker_image: build/docker_image
build/docker_image:
	$(ANNOTATE) $(SUDO) docker build -t "$(DOCKER_IMAGE)" . \
		&> build/docker_image.log
	>&2 egrep '^stderr: ' build/docker_image.log || true
	@echo "docker_image build complete"
	@cat Dockerfile > $@

ext/mesos:
	@echo "ERROR: mesos checkout required at the desired build version"
	@echo "Please check out at the desired build version. For example:"
	@echo "  git clone https://git-wip-us.apache.org/repos/asf/mesos.git ext/mesos"
	@echo "  pushd ext/mesos && git checkout 0.21.1 && popd"
	@exit 1

.PHONY: mesos
mesos: build/mesos.manifest
build/mesos.manifest: build/docker_image ext/mesos
	$(SUDO) rm -rf build/mesos
	cp -rp packages/mesos build
	@# Update package buildinfo
	cat packages/mesos/buildinfo.json \
		| $(JQ) --arg sha "$(MESOS_GIT_SHA)" --arg url "$(MESOS_GIT_URL)" \
		'.single_source.branch = $$sha | .single_source.git = $$url' \
		> build/mesos/buildinfo.json
	cd build/mesos && $(ANNOTATE) mkpanda &> ../mesos.log
	>&2 egrep '^stderr: ' build/mesos.log || true
	@echo 'MESOS_GIT_SHA=$(MESOS_GIT_SHA)' > $@

.PHONY: python
python: build/python.manifest
build/python.manifest: build/docker_image
	@if [[ "$(PYTHON_URL)" == "" ]]; then echo "PYTHON_URL is unset"; exit 1; fi
	$(SUDO) rm -rf build/python
	cp -rp packages/python build
	@# Update package buildinfo
	cat packages/python/buildinfo.json \
		| $(JQ) --arg url "$(PYTHON_URL)" '.single_source.git = $$url' \
		> build/python/buildinfo.json
	cd build/python && $(ANNOTATE) mkpanda &> ../python.log
	>&2 egrep '^stderr: ' build/python.log || true
	@echo 'PYTHON_URL=$(PYTHON_URL)' > $@

.PHONY: marathon
marathon: build/marathon.manifest
build/marathon.manifest: build/docker_image
	@if [[ "$(MARATHON_URL)" == "" ]]; then echo "MARATHON_URL is unset"; exit 1; fi
	$(SUDO) rm -rf build/marathon
	cp -rp packages/marathon build
	@# Update package buildinfo
	cat packages/marathon/buildinfo.json \
		| $(JQ) --arg url "$(MARATHON_URL)" '.single_source.git = $$url' \
		> build/marathon/buildinfo.json
	cd build/marathon && $(ANNOTATE) mkpanda &> ../marathon.log
	>&2 egrep '^stderr: ' build/marathon.log || true
	@echo 'MARATHON_URL=$(MARATHON_URL)' > $@

.PHONY: zookeeper
zookeeper: build/zookeeper.manifest
build/zookeeper.manifest: build/docker_image
	@if [[ "$(ZOOKEEPER_URL)" == "" ]]; then echo "ZOOKEEPER_URL is unset"; exit 1; fi
	$(SUDO) rm -rf build/zookeeper
	cp -rp packages/zookeeper build
	@# Update package buildinfo
	cat packages/zookeeper/buildinfo.json \
		| $(JQ) --arg url "$(ZOOKEEPER_URL)" '.single_source.git = $$url' \
		> build/zookeeper/buildinfo.json
	cd build/zookeeper && $(ANNOTATE) mkpanda &> ../zookeeper.log
	>&2 egrep '^stderr: ' build/zookeeper.log || true
	@echo 'ZOOKEEPER_URL=$(ZOOKEEPER_URL)' > $@

.PHONY: java
java: build/java.manifest
build/java.manifest: build/docker_image
	@if [[ "$(JAVA_URL)" == "" ]]; then echo "JAVA_URL is unset"; exit 1; fi
	$(SUDO) rm -rf build/java
	cp -rp packages/java build
	@# Update package buildinfo
	cat packages/java/buildinfo.json \
		| $(JQ) --arg url "$(JAVA_URL)" '.single_source.git = $$url' \
		> build/java/buildinfo.json
	cd build/java && $(ANNOTATE) mkpanda &> ../java.log
	>&2 egrep '^stderr: ' build/java.log || true
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
prereqs: gtar docker sha256sum sed jq

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

.PHONY: jq
jq:
	@hash $(JQ) 2>/dev/null || { echo >&2 "ERROR: jq required"; exit 1; }
