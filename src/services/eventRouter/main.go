package main

import (
	"eventRouter/main/modules"
	"fmt"
	"html"
	"log"
	"net"
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
	kafkaServers := []string{os.Getenv("KAFKA_BOOTSTRAP_SERVERS")}

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		log.Println("STARTING KAFKA ", kafkaServers)
		_, err := modules.NewKafkaClient(kafkaServers)

		modules.SmokeTestKafka(kafkaServers, "test-topic")

		if err != nil {
			log.Fatal("KAFKA CLIENT", err)
		}

		fmt.Fprintf(w, "event router, %q", html.EscapeString(r.URL.Path))
	})

	ln, err := net.Listen("tcp4", ":"+port)
	if err != nil {
		log.Fatalf("Failed to bind to IPv4 on port %s: %v", port, err)
	}

	log.Printf("Listening on 0.0.0.0:%s (IPv4 enforced)", port)

	if err := http.Serve(ln, nil); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
