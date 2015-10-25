package main

import (
	log "github.com/Sirupsen/logrus"
	"os"
	//"text/template"
)

func generate(config Config, gentype string) {
	log.Info("Generating configuration for ", config.ClusterName, " in ", config.OutputDir, " for installation type ", gentype)
	switch gentype {
	case "onprem":
		do_onprem(config)
		build_packages()
	case "aws":
	case "chef":
	default:
		log.Error(gentype, " is not a supported installation type. Exiting")
		os.Exit(1)
	}
}

func do_onprem(config Config) {
	log.Info("Starting on premise configuration generation...")

}

func build_packages() {

}
