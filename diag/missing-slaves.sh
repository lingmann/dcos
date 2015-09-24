#!/bin/bash

diff <(gcloud compute instances list | grep verizon-slave | awk '{ print $4 }' | sort) \
  <(curl -fsSL http://104.154.45.237:5050/master/state.json | python -m "json.tool" | grep 'slave(1)' | cut -d"@" -f2 | cut -d":" -f1 | sort)
