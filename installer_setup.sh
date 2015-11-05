#!/bin/bash

#check for pkgpanda and grab if necessary
if [ ! -d ext/pkgpanda ]; then
  git clone git@github.com:mesosphere/pkgpanda.git ext/pkgpanda
else
  git -C ext/pkgpanda fetch origin -t +refs/heads/*:refs/remotes/origin/*
fi
#check for dcos-image and grab if necessary
if [ ! -d ext/dcos-image ]; then
  git clone git@github.com:mesosphere/dcos-image.git ext/dcos-image
else
  git -C ext/dcos-image fetch origin -t +refs/heads/*:refs/remotes/origin/*
fi
