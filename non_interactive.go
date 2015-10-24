package main

import (
	log "github.com/Sirupsen/logrus"
)

func NonInteractive() {
	log.Info("Checking configuration in ", *configpath)
	config := GetConfig(*configpath)

}
