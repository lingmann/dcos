package main

import (
	log "github.com/Sirupsen/logrus"
)

func NonInteractive() {
	log.Info("Checking configuration in ", *configpath)
	config := GetConfig(*configpath)
	log.Info("Building configuration for ", config.ClusterName, " cluster...")
	generate(config)
}
