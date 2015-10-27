package main

import (
	"fmt"
)

func ValidateDependencies(config Config) {
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
	case "cloud-dynamic":
		if check_property(config.NumMasters) {
			continue
		} else {
			blowup("cloud-dynamic", "num_masters", *config.MasterDiscovery)
		}
	}
	// Test dependencies for exhibitor storage backend
	switch config.ExhibitorStorageBackend {
	// Zookeeper Backend
	case "zookeeper":
		if check_property(config.ExhibitorZkHosts) {
			continue
		} else {
			blowup("zookeeper", "exhibitor_zk_hosts", *config.MasterDiscovery)
		}
		if check_property(config.ExhibitorZkPath) {
			continue
		} else {
			blowup("zookeeper", "exhibitor_zk_path", *config.MasterDiscovery)
		}
	// S3 Backend
	case "aws_s3":
		if check_property(config.AwsAccessKeyId) {
			continue
		} else {
			blowup("aws_s3", "aws_access_key_id", *config.MasterDiscovery)
		}
		if check_property(config.AwsRegion) {
			continue
		} else {
			blowup("aws_s3", "aws_region", *config.MasterDiscovery)
		}
		if check_property(config.AwsSecretAccessKey) {
			continue
		} else {
			blowup("aws_s3", "aws_secret_access_Key", *config.MasterDiscovery)
		}
		if check_property(config.S3Bucket) {
			continue
		} else {
			blowup("aws_s3", "s3_bucket", *config.MasterDiscovery)
		}
		if check_property(config.S3Prefix) {
			continue
		} else {
			blowup("aws_s3", "s3_prefix", *config.MasterDiscovery)
		}
	case "shared_filesystem":
		if check_property(config.ExhibitorFsConfigPath) {
			continue
		} else {
			blowup("shared_filesystem", "exhibitor_fs_config_Path", *config.MasterDiscovery)
		}
	}
}

func blowup(required_key string, requiring_key string, case_key string) {
	log.Error(fmt.Sprintf("Must set %s when using %s type %s. Exiting.", required_key, requiring_key, case_key))
	os.Exit(1)
}
