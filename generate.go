package main

import (
	"fmt"
	log "github.com/Sirupsen/logrus"
	"gopkg.in/yaml.v2"
	"io/ioutil"
	"os"
	"strings"
	"text/template"
)

func generate(config Config, gentype string) {
	if gentype != "onprem" {
		log.Error(gentype, " is not a supported installation type. Exiting")
		os.Exit(1)
	}
	log.Info("Generating configuration for ", config.ClusterName, " in ", config.OutputDir, " for installation type ", gentype)
	// Get templates to load per provider
	templates := get_template_tree(config)
	// Validate that the configuration satisfies dependencies
	ValidateDependencies(config)
	// Render the templates
	RenderTemplates(config, templates)

}

func get_template_tree(config Config) []string {
	searchPath := fmt.Sprintf("templates/:templates/%s/config.yaml:templates/%s/master-discovery/%s/config.yaml:templates/%s/exhibitor-storage-backend/%s/config.yaml", *gentype, *gentype, config.MasterDiscovery, *gentype, config.ExhibitorStorageBackend)
	log.Debug("Template search path ", searchPath)
	return strings.Split(searchPath, ":")
}

func RenderTemplates(config Config, templates []string) {
	for _, temp := range templates {
		log.Info("Rendering template ", temp)
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

func check_property(property interface{}) bool {
	switch property.(type) {
	case string:
		if len(property.(string)) == 0 {
			return false
		} else {
			return true
		}
	case []string:
		if len(property.([]string)) == 0 {
			return false
		} else {
			return true
		}
	}
	return true
}
