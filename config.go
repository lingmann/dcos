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
	ClusterName  *string `yaml:"cluster_name"`
	BootstrapUrl *string `yaml:"bootstrap_url"`
	// Set with defaults
	GcDelay           *string   `yaml:"gc_delay"`
	DockerRemoveDelay *string   `yaml:"docker_remove_delay"`
	DnsResolvers      *[]string `yaml:"dns_resolvers"`
	Weights           *string   `yaml:"weights"`
	Roles             *string   `yaml:"roles"`
	Quorum            *string   `yaml:"quorum"`
	// Set by user
	MasterDiscovery *string `yaml:"master_discovery"`
	// Static
	MasterList *[]string `yaml:"master_list"`
	// Cloud-dynamic
	NumMasters *string `yaml:"num_masters"`
	// Keepalived
	KeepalivedRouterId         *string `yaml:"keepalived_router_id"`
	KeepalivedInterface        *string `yaml:"keepalived_interface"`
	KeepalivedPass             *string `yaml:"keepalived_pass"`
	KeepalivedVirtualIpaddress *string `yaml:"keepalived_virtual_ipaddress"`
	// Exhibitor storage backend
	ExhibitorStorageBackend *string `yaml:"exhibitor_storage_backend"`
	// Zookeeper requires:
	ExhibitorZkHosts *[]string `yaml:"exhibitor_zk_hosts"`
	ExhibitorZkPath  *string   `yaml:"exhibitor_zk_path"`
	// AWS S3 requires:
	AwsAccessKeyId     *string `yaml:"aws_access_key_id"`
	AwsRegion          *string `yaml:"aws_region"`
	AwsSecretAccessKey *string `yaml:"aws_secret_access_key"`
	S3Bucket           *string `yaml:"s3_bucket"`
	S3Prefix           *string `yaml:"s3_prefix"`
	// Shared filesystem requires:
	ExhibitorFsConfigPath *string `yaml:"exhibitor_fs_config_path"`
	// Config from ENV
	BootstrapId *string
	ChannelName *string
	DcosDir     *string
	OutputDir   *string
}

const (
	DefaultNumMasters        = "3"
	DefaultRoles             = "slave_public"
	DefaultWeights           = "slave_public=1"
	DefaultQuorum            = "3"
	DefaultDockerRemoveDelay = "2hrs"
	DefaultGcDelay           = "2hrs"
)

func GetConfig(path string) (config Config) {
	config.GcDelay = DefaultGcDelay
	config.DockerRemoveDelay = DefaultDockerRemoveDelay
	//config.DnsResolves = DefaultDnsResolvers
	config.Weights = DefaultWeights
	config.Roles = DefaultRoles
	config.Quorum = DefaultQuorum
	// Read in the actual config and override stuff
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
