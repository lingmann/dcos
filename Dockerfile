FROM ubuntu:14.04.1
MAINTAINER support+docker@mesosphere.io

RUN apt-get -qq update && apt-get -y install \
  autoconf \
  automake \
  make \
  gcc \
  cpp \
  patch \
  python-dev \
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
  ruby-dev
RUN gem install --verbose fpm
WORKDIR /dcos
