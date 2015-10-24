package main

import (
	"gopkg.in/yaml.v2"
	"io/ioutil"
)

func GetConfig(path string) (config Config) {
	cf, err := ioutil.ReadFile(path)
	// Maybe generate base config if not found later
	CheckError(err)
	// Unmarshal YAML config to struct and return
	err = yaml.Unmarshal(cf, &config)
	CheckError(err)
	return config
}
