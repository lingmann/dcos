FROM ubuntu:14.04
MAINTAINER docker@mesosphere.io

RUN apt-get update
RUN apt-get install -y python3-setuptools
ADD . /tmp/package

RUN cd /tmp/package && python3 setup.py install
RUN rm -rf /tmp/package

CMD dcos-history
