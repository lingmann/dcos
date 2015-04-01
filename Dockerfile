FROM ubuntu:14.04
MAINTAINER docker@mesosphere.io

RUN apt-get update
RUN apt-get install -y python python-dev python-pip python-pycurl
ADD . /tmp/package

RUN cd /tmp/package && python setup.py install
RUN rm -rf /tmp/package

CMD dcos-history
