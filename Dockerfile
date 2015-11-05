FROM python:3.4.3-slim
MAINTAINER support+dcos@mesosphere.io

#TODO: do we really need curl, pxz?

RUN apt-get update && \
  apt-get install -y \
    curl \
    pxz \
    ssh \
    git \
    gcc && \
  rm -rf /var/lib/apt/lists/* && apt-get clean

COPY . /dcos-web-installer

WORKDIR /dcos-web-installer

RUN pip3 install -r requirements.txt
RUN cd ext/pkgpanda && pip3 install .

VOLUME /genconf

EXPOSE 9000
ENTRYPOINT /dcos-web-installer/run