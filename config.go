package main

import (
	log "github.com/Sirupsen/logrus"
	"gopkg.in/yaml.v2"
	"io/ioutil"
	"os"
)

// Configuration from YAML
type Config struct {
	ClusterName       string   `yaml:"cluster_name"`
	BootstrapUrl      string   `yaml:"bootstrap_url"`
	NumMasters        string   `yaml:"num_masters"`
	GcDelay           string   `yaml:"gc_delay"`
	DockerRemoveDelay string   `yaml:"docker_remove_delay"`
	DnsResolvers      []string `yaml:"dns_resolvers"`
	MasterDiscovery   struct {
		CloudDynamic struct {
			Set bool `yaml:"set"`
		} `yaml:"cloud_dynamic"`
		Static struct {
			Set        bool   `yaml:"set"`
			MasterList string `yaml:"master_list"`
		} `yaml:"static"`
		Vrrp struct {
			Set                        bool   `yaml:"set"`
			KeepalivedRouterId         string `yaml:"keepalived_router_id"`
			KeepalivedInterface        string `yaml:"keepalived_interface"`
			KeepalivedPass             string `yaml:"keepalived_pass"`
			KeepalivedVirtualIpaddress string `yaml:"keepalived_virtual_ipaddress"`
		} `yaml:"vrrp"`
	} `yaml:"master_discovery"`
	ExhibitorStorageBackend struct {
		Zookeeper struct {
			Set              bool     `yaml:"set"`
			ExhibitorZkHosts []string `yaml:"exhibitor_zk_hosts"`
			ExhibitorZkPath  string   `yaml:"exhibitor_zk_path"`
		} `yaml:"zookeeper"`
		AwsS3 struct {
			Set                bool   `yaml:"set"`
			AwsAccessKeyId     string `yaml:"aws_access_key_id"`
			AwsRegion          string `yaml:"aws_region"`
			AwsSecretAccessKey string `yaml:"aws_secret_access_key"`
			S3Bucket           string `yaml:"s3_bucket"`
			S3Prefix           string `yaml:"s3_prefix"`
		} `yaml:"aws_s3"`
		SharedFilesystem struct {
			Set                   bool   `yaml:"set"`
			ExhibitorFsConfigPath string `yaml:"exhibitor_fs_config_path"`
		} `yaml:"shared_filesystem"`
	} `yaml:"exhibitor_storage_backend"`
	// Config from ENV
	BootstrapId string
	ChannelName string
}

func GetConfig(path string) (config Config) {
	cf, err := ioutil.ReadFile(path)
	// Maybe generate base config if not found later
	CheckError(err)
	// Unmarshal YAML config to struct and return
	err = yaml.Unmarshal(cf, &config)
	CheckError(err)
	// Get ENV based configuration
	config.BootstrapId = os.Getenv("DCOS_BOOTSTRAP_ID")
	CheckEnv(config.BootstrapId, "DCOS_BOOTSTRAP_ID")
	config.ChannelName = os.Getenv("DOCS_CHANNEL_NAME")
	CheckEnv(config.ChannelName, "DCOS_CHANNEL_NAME")
	return config
}

func CheckEnv(env string, name string) {
	if len(env) == 0 {
		log.Error(name, " is not set. Exiting.")
		os.Exit(1)
	}
}
