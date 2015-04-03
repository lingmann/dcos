SHELL        := /bin/bash
EMPTY        :=
SPACE        := $(EMPTY) $(EMPTY)
DOCKER_IMAGE := dcos-builder
UID          := $(shell id -u)
GID          := $(shell id -g)
PROJECT_ROOT := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
ENVSUBST     ?= envsubst
SUDO         ?= sudo
JQ           ?= jq
MKPANDA      ?= mkpanda --repository-path=$(PROJECT_ROOT)/build/repo
ANNOTATE     ?= $(PROJECT_ROOT)/bin/annotate.sh
DOCKER_RUN   ?= $(SUDO) docker run -v $(CURDIR):/dcos \
	-e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) \
	-e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)

ifeq ($(origin PKGPANDA_GIT_URL), undefined)
PKGPANDA_GIT_URL := $(PROJECT_ROOT)/ext/pkgpanda
endif

ifeq ($(origin PKGPANDA_GIT_SHA), undefined)
PKGPANDA_GIT_SHA := $(shell cd ext/pkgpanda 2>/dev/null && git rev-parse HEAD)
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
all: tree

.PHONY: tree
tree: | build/docker_image
	@rm -rf packages/bootstrap_tmp dist packages/active.json packages/bootstrap.tar.xz
	@mkdir -p dist/config
	@cd packages && mkpanda tree --mkbootstrap
	@cp packages/bootstrap.tar.xz dist
	@# Append dcos-config--setup (env specific config pkg) to default active.json
	@jq '. + ["dcos-config--setup"]' \
		packages/active.json > dist/config/active.json
	@# Set up manifest contents
	@cat build/*.manifest > dist/dcos-$(PKG_VER)-$(PKG_REL).manifest
	@# Checksum
	@cd dist && sha256sum *.tar.xz > \
		dcos-$(PKG_VER)-$(PKG_REL).sha256

.PHONY: publish
publish: | build/docker_image
	@# Use docker image as a convenient way to run AWS CLI tools
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/ s3://downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/ \
		--recursive
	@echo "Bootstrap URL's:"
	@echo "  Cloudfront: https://downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/"
	@echo "  Direct: https://s3.amazonaws.com/downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/"

.PHONY: publish-link
publish-link: publish | build/docker_image
	@if [[ "$(PUBLISH_LINK)" == "" ]]; then echo "PUBLISH_LINK is unset"; exit 1; fi
	@# Use docker image as a convenient way to run AWS CLI tools
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/bootstrap.tar.xz s3://downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/dcos-$(PKG_VER)-$(PKG_REL).manifest \
		s3://downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/dcos.manifest
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/dcos-$(PKG_VER)-$(PKG_REL).sha256 \
		s3://downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/dcos.sha256
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/config
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/config/active.json \
		s3://downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/config/active.json

debug: | build/docker_image
	$(DOCKER_RUN) \
		-i -t -e "PKG_VER=$(PKG_VER)" -e "PKG_REL=$(PKG_REL)" -e "MAKEFLAGS=$(MAKEFLAGS)" \
		$(DOCKER_IMAGE) bash

.PHONY: docker_image
docker_image: | build/docker_image
build/docker_image:
	$(ANNOTATE) $(SUDO) docker build -t "$(DOCKER_IMAGE)" . \
		&> build/docker_image.log
	>&2 egrep '^stderr: ' build/docker_image.log || true
	@echo "docker_image build complete"
	@cat Dockerfile > $@

.PHONY: mesos
mesos: | build/mesos.manifest
build/mesos.manifest: | build/mesos-buildenv.manifest
build/mesos.manifest: | build/docker_image
	$(SUDO) rm -rf build/mesos
	cp -rp packages/mesos build
	cd build/mesos && $(ANNOTATE) $(MKPANDA) &> ../mesos.log
	>&2 egrep '^stderr: ' build/mesos.log || true
	$(MKPANDA) remove mesos || true
	$(MKPANDA) add build/mesos/*.tar.xz
	touch $@

.PHONY: mesos-buildenv
mesos-buildenv: | build/mesos-buildenv.manifest
build/mesos-buildenv.manifest: | build/docker_image
	$(SUDO) rm -rf build/mesos-buildenv
	cp -rp packages/mesos-buildenv build
	cd build/mesos-buildenv && $(ANNOTATE) $(MKPANDA) &> ../mesos-buildenv.log
	$(MKPANDA) remove mesos-buildenv || true
	$(MKPANDA) add build/mesos-buildenv/*.tar.xz
	touch $@

.PHONY: python
python: | build/python.manifest
build/python.manifest: | build/docker_image
	@if [[ "$(PYTHON_URL)" == "" ]]; then echo "PYTHON_URL is unset"; exit 1; fi
	$(SUDO) rm -rf build/python
	cp -rp packages/python build
	@# Update package buildinfo
	cat packages/python/buildinfo.json \
		| $(JQ) --arg url "$(PYTHON_URL)" '.single_source.git = $$url' \
		> build/python/buildinfo.json
	cd build/python && $(ANNOTATE) $(MKPANDA) &> ../python.log
	>&2 egrep '^stderr: ' build/python.log || true
	$(MKPANDA) remove python || true
	$(MKPANDA) add build/python/*.tar.xz
	@echo 'PYTHON_URL=$(PYTHON_URL)' > $@

.PHONY: python-requests
python-requests: | build/python-requests.manifest build/python.manifest
build/python-requests.manifest: | build/docker_image
	$(SUDO) rm -rf build/python-requests
	cp -rp packages/python-requests build
	cd build/python-requests && $(ANNOTATE) $(MKPANDA) &> ../python-requests.log
	$(MKPANDA) remove python-requests || true
	$(MKPANDA) add build/python-requests/*.tar.xz
	touch $@

.PHONY: dcos-cli
dcos-cli: | build/dcos-cli.manifest build/python.manifest
dcos-cli: | build/python-requests.manifest
build/dcos-cli.manifest: | build/docker_image
	$(SUDO) rm -rf build/dcos-cli
	cp -rp packages/dcos-cli build
	cd build/dcos-cli && $(ANNOTATE) $(MKPANDA) &> ../dcos-cli.log
	$(MKPANDA) remove dcos-cli || true
	$(MKPANDA) add build/dcos-cli/*.tar.xz
	touch $@

.PHONY: marathon
marathon: | build/marathon.manifest
build/marathon.manifest: | build/java.manifest build/docker_image
	@if [[ "$(MARATHON_URL)" == "" ]]; then echo "MARATHON_URL is unset"; exit 1; fi
	$(SUDO) rm -rf build/marathon
	cp -rp packages/marathon build
	@# Update package buildinfo
	cat packages/marathon/buildinfo.json \
		| $(JQ) --arg url "$(MARATHON_URL)" '.single_source.git = $$url' \
		> build/marathon/buildinfo.json
	cd build/marathon && $(ANNOTATE) $(MKPANDA) &> ../marathon.log
	>&2 egrep '^stderr: ' build/marathon.log || true
	$(MKPANDA) remove marathon || true
	$(MKPANDA) add build/marathon/*.tar.xz
	@echo 'MARATHON_URL=$(MARATHON_URL)' > $@

.PHONY: exhibitor
exhibitor: | build/exhibitor.manifest
build/exhibitor.manifest: | build/java.manifest build/docker_image
	$(SUDO) rm -rf build/exhibitor
	cp -rp packages/exhibitor build
	cd build/exhibitor && $(ANNOTATE) $(MKPANDA) &> ../exhibitor.log
	>&2 egrep '^stderr: ' build/exhibitor.log || true
	$(MKPANDA) remove exhibitor || true
	$(MKPANDA) add build/exhibitor/*.tar.xz
	touch $@

.PHONY: java
java: | build/java.manifest
build/java.manifest: | build/docker_image
	@if [[ "$(JAVA_URL)" == "" ]]; then echo "JAVA_URL is unset"; exit 1; fi
	$(SUDO) rm -rf build/java
	cp -rp packages/java build
	@# Update package buildinfo
	cat packages/java/buildinfo.json \
		| $(JQ) --arg url "$(JAVA_URL)" '.single_source.git = $$url' \
		> build/java/buildinfo.json
	cd build/java && $(ANNOTATE) $(MKPANDA) &> ../java.log
	>&2 egrep '^stderr: ' build/java.log || true
	$(MKPANDA) remove java || true
	$(MKPANDA) add build/java/*.tar.xz
	@echo 'JAVA_URL=$(JAVA_URL)' > $@

.PHONY: mesos-dns
mesos-dns: | build/mesos-dns.manifest
build/mesos-dns.manifest: | build/docker_image
	$(SUDO) rm -rf build/mesos-dns
	cp -rp packages/mesos-dns build
	cd build/mesos-dns && $(ANNOTATE) $(MKPANDA) &> ../mesos-dns.log
	>&2 egrep '^stderr: ' build/mesos-dns.log || true
	$(MKPANDA) remove mesos-dns || true
	$(MKPANDA) add build/mesos-dns/*.tar.xz
	touch $@

.PHONY: pkgpanda
pkgpanda: | build/pkgpanda.manifest build/python-requests.manifest
build/pkgpanda.manifest: | build/python.manifest build/docker_image
	$(SUDO) rm -rf build/pkgpanda
	cp -rp packages/pkgpanda build
	@# Update package buildinfo
	cat packages/pkgpanda/buildinfo.json \
		| $(JQ) --arg sha "$(PKGPANDA_GIT_SHA)" --arg url "$(PKGPANDA_GIT_URL)" \
		'.single_source.branch = $$sha | .single_source.git = $$url' \
		> build/pkgpanda/buildinfo.json
	cd build/pkgpanda && $(ANNOTATE) $(MKPANDA) &> ../pkgpanda.log
	>&2 egrep '^stderr: ' build/pkgpanda.log || true
	$(MKPANDA) remove pkgpanda || true
	$(MKPANDA) add build/pkgpanda/*.tar.xz
	@echo 'PKGPANDA_GIT_SHA=$(PKGPANDA_GIT_SHA)' > $@

.PHONY: nginx
nginx: | build/nginx.manifest
build/nginx.manifest: | build/docker_image
	$(SUDO) rm -rf build/nginx
	cp -rp packages/nginx build
	cd build/nginx && $(ANNOTATE) $(MKPANDA) &> ../nginx.log
	>&2 egrep '^stderr: ' build/nginx.log || true
	$(MKPANDA) remove nginx || true
	$(MKPANDA) add build/nginx/*.tar.xz
	touch $@

.PHONY: dcos-ui
dcos-ui: | build/dcos-ui.manifest
build/dcos-ui.manifest: | build/docker_image
	$(SUDO) rm -rf build/dcos-ui
	cp -rp packages/dcos-ui build
	cd build/dcos-ui && $(ANNOTATE) $(MKPANDA) &> ../dcos-ui.log
	>&2 egrep '^stderr: ' build/dcos-ui.log || true
	$(MKPANDA) remove dcos-ui || true
	$(MKPANDA) add build/dcos-ui/*.tar.xz
	touch $@

.PHONY: hadoop
hadoop: | build/hadoop.manifest
build/hadoop.manifest: | build/docker_image
	$(SUDO) rm -rf build/hadoop
	cp -rp packages/hadoop build
	cd build/hadoop && $(ANNOTATE) $(MKPANDA) &> ../hadoop.log
	>&2 egrep '^stderr: ' build/hadoop.log || true
	$(MKPANDA) remove hadoop || true
	$(MKPANDA) add build/hadoop/*.tar.xz
	touch $@

.PHONY: hdfs-mesos
hdfs-mesos: | build/hdfs-mesos.manifest
build/hdfs-mesos.manifest: | build/docker_image
build/hdfs-mesos.manifest: | build/hadoop.manifest build/java.manifest
	$(SUDO) rm -rf build/hdfs-mesos
	cp -rp packages/hdfs-mesos build
	cd build/hdfs-mesos && $(ANNOTATE) $(MKPANDA) &> ../hdfs-mesos.log
	>&2 egrep '^stderr: ' build/hdfs-mesos.log || true
	$(MKPANDA) remove hdfs-mesos || true
	$(MKPANDA) add build/hdfs-mesos/*.tar.xz
	touch $@

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
prereqs: docker sha256sum sed jq

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
