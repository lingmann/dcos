package main

import (
	"flag"
	"fmt"
	log "github.com/Sirupsen/logrus"
	"os"
)

// CLI Flags
var mode = flag.String("mode", "NOT SET", "Interactive configuration builder mode.")
var verbose = flag.Bool("v", false, "Log verbosity true.")
var configpath = flag.String("config", "dcos-config.yaml", "/path/to/dcos-config.yaml")
var gentype = flag.String("type", "onprem", "Installation type. Available candidates: onprem, chef, aws")

func main() {
	flag.Parse()
	if *verbose {
		log.SetLevel(log.DebugLevel)
		log.Debug("Log level DEBUG")
	} else {
		log.SetLevel(log.InfoLevel)
		log.Info("Log level INFO")
	}
	if *gentype != "onprem" {
		log.Error(gentype, " is not a supported installation type. Exiting")
		os.Exit(1)
	}

	// Execute the correct console mode
	switch *mode {
	case "web":
		log.Info("Starting configuration mode in browser.")
		Web()
	case "non-interactive":
		log.Info("Starting configuration mode in non-interactive mode.")
		NonInteractive()
	case "interactive":
		log.Info("Starting configuration mode in interactive mode.")
	default:
		log.Error(fmt.Sprintf("%s is not a known configuration mode.", *mode))
		//showDefaults()
		os.Exit(1)
	}
}
