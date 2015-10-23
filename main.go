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
	ClusterName             string   `yaml:"cluster_name"`
	BootstrapUrl            string   `yaml:"bootstrap_url"`
	DnsResolvers            string   `yaml:"dns_resolvers"`
	MasterDiscovery         string   `yaml:"master_discovery"`
	MasterStaticList        []string `yaml:"master_static_list"`
	ExhibitorStorageBackend string   `yaml:"exhibitor_storage_backend"`
	ExhibitorZkHosts        []string `yaml:"exhibitor_zk_hosts"`
	ExhibitorZkPath         string   `yaml:"exhibitor_zk_path"`
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
