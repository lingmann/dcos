package main

import (
	log "github.com/Sirupsen/logrus"
	"os"
)

func CheckError(err error) {
	if err != nil {
		log.Error(err)
		os.Exit(1)
	}
}

func CleanupTempTemplates() {

}
