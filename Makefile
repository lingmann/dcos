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
	@if [[ -f build/dcos.manifest ]]; then echo "ERROR: Please remove build/dcos.manifest before running set-version"; exit 1; fi
	@echo "Setting PKG_VER and PKG_REL in build/dcos.manifest"
	@mkdir -p build
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
	@echo "Publishing to:"
	@echo "  Cloudfront: https://downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/"
	@echo "  Direct: https://s3.amazonaws.com/downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/"
	@# Use docker image as a convenient way to run AWS CLI tools
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/ s3://downloads.mesosphere.io/dcos/$(PKG_VER)-$(PKG_REL)/ \
		--recursive

.PHONY: publish-link
publish-link: publish | build/docker_image
	@if [[ "$(PUBLISH_LINK)" == "" ]]; then echo "PUBLISH_LINK is unset"; exit 1; fi
	@echo "Publishing to:"
	@echo "  Cloudfront: https://downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/"
	@echo "  Direct: https://s3.amazonaws.com/downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/"
	@# Use docker image as a convenient way to run AWS CLI tools
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 mb \
		s3://downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/
	@$(DOCKER_RUN) $(DOCKER_IMAGE) aws s3 cp \
		/dcos/dist/ s3://downloads.mesosphere.io/dcos/$(PUBLISH_LINK)/ \
		--recursive

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

.PHONY: clean
clean:
	$(SUDO) rm -rf build dist

.PHONY: distclean
distclean: clean
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
