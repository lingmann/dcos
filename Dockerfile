FROM ubuntu:14.04.2
MAINTAINER support+docker@mesosphere.io

RUN apt-get -qq update && apt-get -y install \
  autoconf \
  automake \
  make \
  gcc \
  cpp \
  patch \
  python-dev \
  python-pip \
  git \
  libtool \
  default-jdk \
  default-jre \
  gzip \
  zlib1g-dev \
  libcurl4-openssl-dev \
  python-setuptools \
  dpkg-dev \
  libsasl2-dev \
  maven \
  libapr1-dev \
  libsvn-dev \
  ruby \
  curl \
  wget \
  scala \
  xz-utils \
  libpopt-dev \
  libnl-3-dev \
  libnl-genl-3-dev \
  linux-headers-3.19.0-21-generic \
  pkg-config
RUN pip install awscli
