SHELL     := /bin/bash
PKG_VER   ?= $(shell python -c "import history ; print(history.__version__)")
REL_PATCH ?= $(shell date -u +'%Y%m%d%H%M%S')

.PHONY: help
help:
	@echo "setup to create a virtual environment with all dependencies"
	@exit 0

.PHONY: setup
setup:
	pyvenv env; \
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

.PHONY: run
run:
	docker run -p 5000:500 -e MASTER_URLS="$(MASTER_URLS)" mesosphere/dcos-history-service:$(PKG_VER)

.PHONY: ovh
ovh:
	http PUT http://srv2.hw.ca1.mesosphere.com:8080/v2/apps/dcos/service/history < ovh-stage-marathon.json
