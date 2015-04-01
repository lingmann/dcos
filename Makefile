SHELL     := /bin/bash
PKG_VER   ?= $(shell python -c "import history ; print history.__version__")
REL_PATCH ?= $(shell date -u +'%Y%m%d%H%M%S')
SHA       ?= $(shell git rev-parse --short HEAD)
ITEMS      = $(REL_MAJOR) $(REL_MINOR) $(REL_PATCH) $(DIST)$(DIST_VER) $(SHA)
PKG_REL    = $(subst $(SPACE),.,$(strip $(ITEMS)))

.PHONY: help
help:
	@echo ""
	@exit 0

.PHONY: setup
setup:
	virtualenv env; \
	source env/bin/activate; \
	pip install requests psutil; \
	python setup.py develop

.PHONY: destroy
destroy:
	deactivate
	rm -rf env

.PHONY: test
test:
	source env/bin/activate; \
	pip install tox; \
	tox

.PHONY: dist
dist:
	echo "Build version $(PKG_VER)"
	docker build -t mesosphere/dcos-history-service:$(PKG_VER) .

.PHONY: dist
push: dist
	docker push mesosphere/dcos-history-service:$(PKG_VER)


run:
	docker run -p 5000:500 -e MASTER_URLS="http://srv2.hw.ca1.mesosphere.com:5050" mesosphere/dcos-history-service:$(PKG_VER)


