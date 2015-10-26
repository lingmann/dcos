package main

import (
	"fmt"
	"strings"
)

func ValidateDependencies(config) {
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
}

func blowup(required_key string, requiring_key string, case_key string) {
	log.Error(fmt.Sprintf("Must set %s when using %s type %s. Exiting.", required_key, requiring_key, case_key))
	os.Exit(1)
}
