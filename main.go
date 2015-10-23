package main

import (
	"flag"
	log "github.com/Sirupsen/logrus"
	"os"
)

// CLI Flags
var mode = flag.String("interactive", "web", "Interactive configuration builder mode.")
var verbose = flag.Bool("v", false, "Log verbosity true.")

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
		ExhibitorZkHosts []string `yaml:"exhibitor_zk_hosts"`
		ExhibitorZkPath  string   `yaml:"exhibitor_zk_path"`
	} `yaml:"exhibitor_storage_backend"`
}

func main() {
	flag.Parse()
	if *verbose {
		log.SetLevel(log.DebugLevel)
		log.Debug("Log level DEBUG")
	} else {
		log.SetLevel(log.InfoLevel)
		log.Info("Log level INFO")
	}

	switch *mode {
	case "web":
		log.Info("Starting configuration mode in browser.")
	case "non-interactive":
		log.Info("Starting configuration mode in non-interactive mode.")
	case "interactive":
		log.Info("Starting configuration mode in interactive mode.")
	default:
		log.Error(mode, " is not a known configuration mode.")
		//showDefaults()
		os.Exit(1)
	}

}
