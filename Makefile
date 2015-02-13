SHELL        := /bin/bash
EMPTY        :=
SPACE        := $(EMPTY) $(EMPTY)
DOCKER_IMAGE := dcos-builder

PKG_VER   ?= 0.0.1
REL_MAJOR ?= 0
REL_MINOR ?= 1
REL_PATCH ?= $(shell date -u +'%Y%m%d%H%M%S')
SHA       ?= $(shell git rev-parse --short HEAD)
ITEMS      = $(REL_MAJOR) $(REL_MINOR) $(REL_PATCH) $(SHA)
PKG_REL    = $(subst $(SPACE),.,$(strip $(ITEMS)))

###############################################################################
# Targets designed to run *outside* the Docker container
###############################################################################

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
	@echo "  SHA: $(SHA)"
	@echo "  MAKEFLAGS: $(MAKEFLAGS)"
	@exit 0

.PHONY: all
all: docker_image ext/mesos
	# Continue the make *inside* the Docker container
	sudo docker run -v $(CURDIR):/dcos $(DOCKER_IMAGE) make \
		MAKEFLAGS=$(MAKEFLAGS) \
		PKG_VER=$(PKG_VER) \
		REL_MAJOR=$(REL_MAJOR) \
		REL_MINOR=$(REL_MINOR) \
		REL_PATCH=$(REL_PATCH) \
		SHA=$(SHA) \
		tarball

.PHONY: docker_image
docker_image:
	sudo docker build -t "$(DOCKER_IMAGE)" .

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

###############################################################################
# Targets designed to run *inside* the Docker container
###############################################################################

.PHONY: tarball
tarball: mesos-make shared-libs
	mkdir -p dist
	cd build/mesos-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL) && \
		tar czvf ../../../../../../dist/dcos-$(PKG_VER)-$(PKG_REL).tgz mesos

.PHONY: mesos-make
mesos-make: configure build/mesos-toor
	cd build/mesos-build && make
	cd build/mesos-build && make install DESTDIR=/dcos/build/mesos-toor

# TODO: Use output of ldd and grab all libs
.PHONY: shared-libs
shared-libs: mesos-make
	cp /usr/lib/x86_64-linux-gnu/libsasl2.so.2 \
		/dcos/build/mesos-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL)/mesos/lib/
	cp /usr/lib/x86_64-linux-gnu/libsvn_delta-1.so.1 \
		/dcos/build/mesos-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL)/mesos/lib/
	cp /usr/lib/x86_64-linux-gnu/libsvn_subr-1.so.1 \
		/dcos/build/mesos-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL)/mesos/lib/
	cp /usr/lib/x86_64-linux-gnu/libapr-1.so.0 \
		/dcos/build/mesos-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL)/mesos/lib/
	cp /usr/lib/x86_64-linux-gnu/libaprutil-1.so.0 \
		/dcos/build/mesos-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL)/mesos/lib/
	cp build/mesos-build/src/java/target/mesos-*.jar \
		/dcos/build/mesos-toor/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL)/mesos/lib/

build/mesos-build:
	mkdir -p build/mesos-build

.PHONY: configure
configure: build/mesos-build bootstrap
	cd build/mesos-build && ../../ext/mesos/configure \
		--prefix=/opt/mesosphere/dcos/$(PKG_VER)-$(PKG_REL)/mesos \
		--enable-optimize --disable-python

.PHONY: bootstrap
bootstrap: ext/mesos
	cd ext/mesos && ./bootstrap

build/mesos-toor:
	mkdir -p build/mesos-toor
