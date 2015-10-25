package main

import (
	"fmt"
	log "github.com/Sirupsen/logrus"
	"os"
	//	"reflect"
	"text/template"
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
	log.Info("Validating parameters for master discovery type ", config.MasterDiscovery)
	// Load required templates
	switch config.MasterDiscovery {
	case "static":
		if len(config.MasterList) == 0 {
			log.Error("Must set master_list when using master_discovery type static. Exiting.")
			os.Exit(1)
		}
		path := build_template_path("master-discovery/static")
		templates = append(templates, path)
	case "keepalived":
		if len(config.KeepalivedRouterId) == 0 {
			log.Error("Must set keepalived_router_id when using master_discovery type keepalived. Exiting.")
			os.Exit(1)
		} else if len(config.KeepalivedInterface) == 0 {
			log.Error("Must set keepalived_interface when using master_discovery type keepalived. Exiting.")
			os.Exit(1)
		} else if len(config.KeepalivedPass) == 0 {
			log.Error("Must set keepalived_pass when using master_discovery type keepalived. Exiting.")
			os.Exit(1)
		} else if len(config.KeepalivedVirtualIpaddress) == 0 {
			log.Error("Must set keepalived_virtual_ipaddress when using master_discovery type keepalived. Exiting.")
			os.Exit(1)
		}
		path := build_template_path("master-discovery/keepalived")
		templates = append(templates, path)
	case "cloud-dynamic":
		if len(config.NumMasters) == 0 {
			log.Error("Must set num_masters when using master_discovery type cloud-dynamic. Exiting.")
			os.Exit(1)
		}
		path := build_template_path("master-discovery/cloud-dynamic")
		templates = append(templates, path)
	}

	RenderTemplates(config, templates)
}

func RenderTemplates(config Config, templates []string) {
	for _, temp := range templates {
		t, err := template.ParseFiles(temp)
		CheckError(err)
		err = t.Execute(os.Stdout, config)
		CheckError(err)
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
