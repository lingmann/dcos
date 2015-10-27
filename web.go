package main

import (
	"flag"
	"fmt"
	log "github.com/Sirupsen/logrus"
	"github.com/gorilla/mux"
	"html/template"
	"net/http"
	"time"
)

// Web console port
var port = flag.String("port", "9000", "The web console port.")

// Define a route struct so we can easily make more later
type Route struct {
	Name        string
	Method      string
	Pattern     string
	HandlerFunc http.HandlerFunc
}

type Routes []Route

var routes = Routes{
	Route{
		"Configurator",
		"GET",
		"/",
		ConfigHandler,
	},
	Route{
		"Configurator",
		"POST",
		"/post",
		PostHandler,
	},
}

// Web entrypoint
func Web() {
	log.Info("Starting web configurator...")
	router := NewRouter()
	// Handle a failure
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%s", *port), router))
}

// Creates new routes using gorilla/mux
func NewRouter() *mux.Router {
	router := mux.NewRouter().StrictSlash(true)
	for _, route := range routes {
		var handler http.Handler

		handler = route.HandlerFunc
		handler = Logger(handler, route.Name)

		router.
			Methods(route.Method).
			Path(route.Pattern).
			Name(route.Name).
			Handler(handler)
	}
	return router
}

// Implements router logging stats
func Logger(inner http.Handler, name string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		inner.ServeHTTP(w, r)

		log.Printf(
			"%s\t%s\t%s\t%s",
			r.Method,
			r.RequestURI,
			name,
			time.Since(start),
		)
	})
}

type PageData struct {
	Title string
}

// The main configuration handler
func ConfigHandler(w http.ResponseWriter, r *http.Request) {
	var data PageData
	data.Title = "TEST"
	t, _ := template.ParseFiles("views/ConfigMain.html")
	t.Execute(w, data)
}

// Post handler
func PostHandler(w http.ResponseWriter, r *http.Request) {
	log.Debug("Post made on ", *port)
}
