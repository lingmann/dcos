package main

import (
	"fmt"
	log "github.com/Sirupsen/logrus"
	"gopkg.in/yaml.v2"
	"io/ioutil"
	"os"
)

// Configuration from YAML
type Config struct {
	ClusterName       string   `yaml:"cluster_name"`
	BootstrapUrl      string   `yaml:"bootstrap_url"`
	GcDelay           string   `yaml:"gc_delay"`
	DockerRemoveDelay string   `yaml:"docker_remove_delay"`
	DnsResolvers      []string `yaml:"dns_resolvers"`
	MasterDiscovery   string   `yaml:"master_discovery"`
	// Static
	MasterList []string `yaml:"master_list"`
	// Cloud-dynamic
	NumMasters string `yaml:"num_masters"`
	// Keepalived
	KeepalivedRouterId         string `yaml:"keepalived_router_id"`
	KeepalivedInterface        string `yaml:"keepalived_interface"`
	KeepalivedPass             string `yaml:"keepalived_pass"`
	KeepalivedVirtualIpaddress string `yaml:"keepalived_virtual_ipaddress"`
	// Exhibitor storage backend
	ExhibitorStorageBackend struct {
		Zookeeper struct {
			ExhibitorZkHosts []string `yaml:"exhibitor_zk_hosts"`
			ExhibitorZkPath  string   `yaml:"exhibitor_zk_path"`
		} `yaml:"zookeeper"`
		AwsS3 struct {
			AwsAccessKeyId     string `yaml:"aws_access_key_id"`
			AwsRegion          string `yaml:"aws_region"`
			AwsSecretAccessKey string `yaml:"aws_secret_access_key"`
			S3Bucket           string `yaml:"s3_bucket"`
			S3Prefix           string `yaml:"s3_prefix"`
		} `yaml:"aws_s3"`
		SharedFilesystem struct {
			ExhibitorFsConfigPath string `yaml:"exhibitor_fs_config_path"`
		} `yaml:"shared_filesystem"`
	} `yaml:"exhibitor_storage_backend"`
	// Config from ENV
	BootstrapId string
	ChannelName string
	DcosDir     string
	OutputDir   string
}

func GetConfig(path string) (config Config) {
	cf, err := ioutil.ReadFile(path)
	// Maybe generate base config if not found later
	CheckError(err)
	// Unmarshal YAML config to struct and return
	err = yaml.Unmarshal(cf, &config)
	CheckError(err)
	// Get output dir and set if does not exist
	config.DcosDir, config.OutputDir = CheckOutputDir()
	// Get ENV based configuration
	config.BootstrapId = CheckEnv(os.Getenv("DCOS_BOOTSTRAP_ID"), "DCOS_BOOTSTRAP_ID")
	config.ChannelName = CheckEnv(os.Getenv("DCOS_CHANNEL_NAME"), "DCOS_CHANNEL_NAME")
	return config
}

func CheckEnv(env string, name string) string {
	if len(env) == 0 {
		log.Error(name, " is not set. Exiting.")
		os.Exit(1)
	}
	log.Info(name, " found in ENV: ", env)
	return env
}

func CheckOutputDir() (string, string) {
	cwd := os.Getenv("HOME")
	servepath := fmt.Sprintf("%s/dcos/serve", cwd)
	dcospath := fmt.Sprintf("%s/dcos", cwd)
	log.Info("Building DCOS directory ", dcospath)
	log.Info("Building output directory ", servepath)
	os.Mkdir(dcospath, 0755)
	os.Mkdir(servepath, 0755)
	return dcospath, servepath
}
