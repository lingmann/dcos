package main

import (
	"fmt"
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
	// Initial array of templates to create
	var templates []string
	// Load required templates
	if config.MasterDiscovery.Static.Set {
		path := build_template_path("master-discovery/static")
		templates = append(templates, path)

	}
}

func build_template_path(appendpath string) (templatepath string) {
	basetemplates := "templates/onprem"
	tempfile := "config.yaml"
	templatepath = fmt.Sprintf("%s/%s/%s", basetemplates, appendpath, tempfile)
	_, err := os.Open(templatepath)
	nopath := os.IsExist(err)
	if !nopath {
		CheckError(err)
	}
	log.Info("Loading template ", templatepath)
	return templatepath

}
func build_packages() {

}
