# Docker build requires that either repos or wheels be placed in an ext directory
FROM python:3.4.3-slim
MAINTAINER support+dcos@mesosphere.io

RUN apt-get update && \
  apt-get install -y \
    curl \
    pxz \
    ssh \
    git \
    gcc && \
  rm -rf /var/lib/apt/lists/* && apt-get clean

COPY . /dcos-installer

WORKDIR /dcos-installer

RUN pip install tox
RUN pip install --find-links=ext dcos_image pkgpanda
RUN pip install .
