package main

import (
	"context"
	"eventRouter/main/modules"
	"eventRouter/main/routes"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/joho/godotenv"
)

func main() {
	// Load .env for local dev; in Kubernetes env vars are injected, so don't fatal.
	if err := godotenv.Load(".env"); err != nil {
		log.Println("[BOOT][WARN] .env not loaded (ok in k8s):", err)
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8085"
	}

	// App lifecycle context (cancels on SIGINT/SIGTERM)
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	// Init Kafka once
	kc, err := modules.NewKafkaClientFromEnv()
	if err != nil {
		log.Fatalf("[BOOT][ERROR] kafka init failed: %v", err)
	}

	// Start routing once (do NOT start from an HTTP handler)
	if err := routes.StartKafkaRouting(ctx, kc); err != nil {
		log.Fatalf("[BOOT][ERROR] routing init failed: %v", err)
	}

	// HTTP routes
	mux := http.NewServeMux()
	mux.HandleFunc("/event", routes.EventRouteHandler)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	srv := &http.Server{
		Handler: mux,
	}

	// IPv4 enforced listener
	ln, err := net.Listen("tcp4", ":"+port)
	if err != nil {
		log.Fatalf("[BOOT][ERROR] failed to bind to IPv4 on port %s: %v", port, err)
	}

	// Graceful shutdown
	go func() {
		<-ctx.Done()
		log.Println("[BOOT] shutdown signal received")

		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		_ = srv.Shutdown(shutdownCtx)
		_ = kc.Close()
	}()

	log.Printf("Listening on 0.0.0.0:%s (IPv4 enforced)", port)

	if err := srv.Serve(ln); err != nil && err != http.ErrServerClosed {
		log.Fatalf("[BOOT][ERROR] server error: %v", err)
	}
}
