package main

import (
	"fmt"
	log "github.com/Sirupsen/logrus"
	"os"
)

func ValidateDependencies(config Config) {
	// Add the base template
	log.Info("Validating parameters for master discovery type ", *config.MasterDiscovery)
	// Load required templates and validate dependencies
	switch config.MasterDiscovery {
	// Static
	case "static":
		if check_property(config.MasterList) {
			pass()
		} else {
			blowup("master_list", "master_discovery", config.MasterDiscovery)
		}
	case "keepalived":
		if check_property(config.KeepalivedRouterId) {
			pass()
		} else {
			blowup("keepalived", "keepalived_router_id", config.MasterDiscovery)
		}
		if check_property(config.KeepalivedInterface) {
			pass()
		} else {
			blowup("keepalived", "keepalived_interface", config.MasterDiscovery)
		}
		if check_property(config.KeepalivedPass) {
			pass()
		} else {
			blowup("keepalived", "keepalived_pass", config.MasterDiscovery)
		}
		if check_property(config.KeepalivedVirtualIpaddress) {
			pass()
		} else {
			blowup("keepalived", "keepalived_virtual_ipaddress", config.MasterDiscovery)
		}
	case "cloud-dynamic":
		if check_property(config.NumMasters) {
			pass()
		} else {
			blowup("cloud-dynamic", "num_masters", config.MasterDiscovery)
		}
	}
	// Test dependencies for exhibitor storage backend
	switch config.ExhibitorStorageBackend {
	// Zookeeper Backend
	case "zookeeper":
		if check_property(config.ExhibitorZkHosts) {
			pass()
		} else {
			blowup("zookeeper", "exhibitor_zk_hosts", config.MasterDiscovery)
		}
		if check_property(config.ExhibitorZkPath) {
			pass()
		} else {
			blowup("zookeeper", "exhibitor_zk_path", config.MasterDiscovery)
		}
	// S3 Backend
	case "aws_s3":
		if check_property(config.AwsAccessKeyId) {
			pass()
		} else {
			blowup("aws_s3", "aws_access_key_id", config.MasterDiscovery)
		}
		if check_property(config.AwsRegion) {
			pass()
		} else {
			blowup("aws_s3", "aws_region", config.MasterDiscovery)
		}
		if check_property(config.AwsSecretAccessKey) {
			pass()
		} else {
			blowup("aws_s3", "aws_secret_access_Key", config.MasterDiscovery)
		}
		if check_property(config.S3Bucket) {
			pass()
		} else {
			blowup("aws_s3", "s3_bucket", config.MasterDiscovery)
		}
		if check_property(config.S3Prefix) {
			pass()
		} else {
			blowup("aws_s3", "s3_prefix", config.MasterDiscovery)
		}
	case "shared_filesystem":
		if check_property(config.ExhibitorFsConfigPath) {
			pass()
		} else {
			blowup("shared_filesystem", "exhibitor_fs_config_Path", config.MasterDiscovery)
		}
	}
}

func pass() {
	log.Debug("Found config match. Passing.")
}

func blowup(required_key string, requiring_key string, case_key string) {
	log.Error(fmt.Sprintf("Must set %s when using %s type %s. Exiting.", required_key, requiring_key, case_key))
	os.Exit(1)
}
