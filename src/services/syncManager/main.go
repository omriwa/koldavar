package main

import (
	"fmt"
	"html"
	"log"
	"net/http"
	"os"

	"github.com/joho/godotenv"
)

func main() {
	err := godotenv.Load(".env")

	if err != nil {
		log.Fatal("Could not load .env")
		return
	}
	port := os.Getenv("PORT")

	log.Println("Starts server on", port)

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "sync manager, %q", html.EscapeString(r.URL.Path))
	})

	log.Fatal(http.ListenAndServe(":"+port, nil))
}
