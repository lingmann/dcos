package main

import (
	"fmt"
	log "github.com/Sirupsen/logrus"
	"gopkg.in/yaml.v2"
	"strings"
	//	"io"
	"io/ioutil"
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
	// Static
	case "static":
		if len(config.MasterList) == 0 {
			log.Error("Must set master_list when using master_discovery type static. Exiting.")
			os.Exit(1)
		}
		path := build_template_path("master-discovery/static")
		templates = append(templates, path)
	// Keepalived
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
func build_packages() {

}
