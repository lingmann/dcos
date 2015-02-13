SHELL        := /bin/bash
EMPTY        :=
SPACE        := $(EMPTY) $(EMPTY)
DOCKER_IMAGE := dcos-builder
UID          := $(shell id -u)
GID          := $(shell id -g)

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
mesos: docker_image ext/mesos
	sudo docker run \
		-e "PKG_VER=$(PKG_VER)" -e "PKG_REL=$(PKG_REL)" -e "MAKEFLAGS=$(MAKEFLAGS)" \
		-v $(CURDIR):/dcos $(DOCKER_IMAGE) bin/build_mesos.sh
	# Chown files modified via Docker mount to UID/GID at time of make invocation
	sudo chown -R $(UID):$(GID) ext/mesos build

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
	@echo "  mkdir -p ext/mesos"
	@echo "  git clone https://git-wip-us.apache.org/repos/asf/mesos.git ext/mesos"
	@echo "  pushd ext/mesos && git checkout 0.21.1 && popd"
	@exit 1

.PHONY: clean
clean:
	sudo rm -rf build

.PHONY: dist-clean
dist-clean: clean
	sudo rm -rf dist ext/*
	sudo docker rmi -f $(DOCKER_IMAGE) || true
