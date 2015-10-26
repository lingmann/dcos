package main

import (
	"fmt"
	log "github.com/Sirupsen/logrus"
	"gopkg.in/yaml.v2"
	"io/ioutil"
	"os"
	"strings"
	"text/template"
)

func generate(config Config, gentype string) {
	log.Info("Generating configuration for ", config.ClusterName, " in ", config.OutputDir, " for installation type ", gentype)
	switch gentype {
	case "onprem":
		// Generate configuration
		do_onprem(config)
		// Build packages
		//build_packages()
	case "aws":
	case "chef":
	default:
		log.Error(gentype, " is not a supported installation type. Exiting")
		os.Exit(1)
	}
}

func get_template_tree(config Config) string {
	searchPath := fmt.Sprintf("templates/:templates/%s/:templates/%s/master-discovery/%s/:templates/%s/exhibitor-storage-backend/%s/", *gentype, *gentype, config.MasterDiscovery, *gentype, config.ExhibitorStorageBackend)
	log.Debug("Template search path ", searchPath)
	return searchPath
}

func blowup(required_key string, requiring_key string, case_key string) {
	log.Error(fmt.Sprintf("Must set %s when using %s type %s. Exiting.", required_key, requiring_key, case_key))
	os.Exit(1)
}

func do_onprem(config Config) {

	log.Info("Starting on premise configuration generation...")
	templates := strings.Split(get_template_tree(config), ":")
	// Add the base template
	log.Info("Validating parameters for master discovery type ", config.MasterDiscovery)
	// Load required templates and validate dependencies
	switch *config.MasterDiscovery {
	// Static
	case "static":
		if check_property(config.MasterList) {
			continue
		} else {
			blowup("master_list", "master_discovery", *config.MasterDiscovery)
		}
	case "keepalived":
		if check_property(config.KeepalivedRouterId) {
			continue
		} else {
			blowup("keepalived", "keepalived_router_id", *config.MasterDiscovery)
		}
		if check_property(config.KeepalivedInterface) {
			continue
		} else {
			blowup("keepalived", "keepalived_interface", *config.MasterDiscovery)
		}
		if check_property(config.KeepalivedPass) {
			continue
		} else {
			blowup("keepalived", "keepalived_pass", *config.MasterDiscovery)
		}
		if check_property(config.KeepalivedVirtualIpaddress) {
			continue
		} else {
			blowup("keepalived", "keepalived_virtual_ipaddress", *config.MasterDiscovery)
		}
	// Cloud dynamic
	case "cloud-dynamic":
		if len(config.NumMasters) == 0 {
			log.Error("Must set num_masters when using master_discovery type cloud-dynamic. Exiting.")
			os.Exit(1)
		}
		path := build_template_path("master-discovery/cloud-dynamic")
		templates = append(templates, path)
	}
	// Test dependencies for exhibitor storage backend
	switch config.ExhibitorStorageBackend {
	// Zookeeper Backend
	case "zookeeper":
		if len(config.ExhibitorZkHosts) == 0 {
			log.Error("Must set exhibitor_zk_hosts when using exhibitor_storage_backend type zookeeper. Exiting.")
			os.Exit(1)
		} else if len(config.ExhibitorZkPath) == 0 {
			log.Error("Must set exhibitor_zk_path when using exhibitor_storage_backend type zookeeper. Exiting.")
			os.Exit(1)
		}
		path := build_template_path("exhibitor-storage-backend/zookeeper")
		templates = append(templates, path)
	// S3 Backend
	case "aws_s3":
		if len(config.AwsAccessKeyId) == 0 {
			log.Error("Must set aws_access_key_id when using exhibitor_storage_backend type aws_s3. Exiting.")
			os.Exit(1)
		} else if len(config.AwsRegion) == 0 {
			log.Error("Must set aws_region when using exhibitor_storage_backend type aws_s3. Exiting.")
			os.Exit(1)
		} else if len(config.AwsSecretAccessKey) == 0 {
			log.Error("Must set aws_secret_access_key when using exhibitor_storage_backend type aws_s3. Exiting.")
			os.Exit(1)
		} else if len(config.S3Bucket) == 0 {
			log.Error("Must set s3_bucket when using exhibitor_storage_backend type aws_s3. Exiting.")
			os.Exit(1)
		} else if len(config.S3Prefix) == 0 {
			log.Error("Must set s3_prefix when using exhibitor_storage_backend type aws_s3. Exiting.")
			os.Exit(1)
		}
		path := build_template_path("exhibitor-storage-backend/aws_s3")
		templates = append(templates, path)

	case "shared_filesystem":
		if len(config.ExhibitorFsConfigPath) == 0 {
			log.Error("Must set exhibitor_fs_config_path when using exhibitor_storage_backend type shared_filesystem. Exiting.")
			os.Exit(1)
		}
		path := build_template_path("exhibitor-storage-backend/filesystem")
		templates = append(templates, path)
	}
	RenderTemplates(config, templates)
}

func RenderTemplates(config Config, templates []string) {
	for _, temp := range templates {
		log.Info("Rendering template ", temp)
		// Parse the tmeplate
		t, err := template.ParseFiles(temp)
		CheckError(err)
		tempfile, err := ioutil.TempFile(config.OutputDir, "template-")
		// Write to the writer
		if err := t.Execute(tempfile, config); err == nil {
			tempFilePath := tempfile.Name()
			log.Info("Writing template ", tempFilePath)
			WriteTemplate(tempFilePath, config)
			log.Info("Cleaning up ", tempFilePath)
			os.Remove(tempFilePath)
		}
		CheckError(err)
	}
}

func WriteTemplate(path string, config Config) {
	type Template struct {
		WriteFiles []struct {
			Path    string `yaml:"path"`
			Content string `yaml:"content"`
		} `yaml:"write_files"`
	}
	var template Template
	tempfile, err := ioutil.ReadFile(path)
	CheckError(err)
	err = yaml.Unmarshal(tempfile, &template)
	CheckError(err)
	for _, file := range template.WriteFiles {
		filePath := fmt.Sprintf("%s%s", config.OutputDir, file.Path)
		log.Info("Writing configuration file ", filePath)
		wd := strings.Join(strings.Split(filePath, "/")[:len(strings.Split(filePath, "/"))-1], "/")
		os.MkdirAll(wd, 0755)
		err := ioutil.WriteFile(filePath, []byte(file.Content), 0644)
		CheckError(err)
	}
}

func build_template_path(appendpath string) (templatepath string) {
	basetemplates := fmt.Sprintf("templates/%s", *gentype)
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

func check_property(property interface{}) bool {
	if property != nil {
		return true
	} else {
		return false
	}
}
