package routes

import (
	"encoding/json"
	"eventRouter/main/modules"
	"log"
	"net/http"
	"os"
	"time"
)

// Single place to init the singleton once (per process)
func getKafkaClient() (*modules.KafkaClient, error) {
	servers := []string{os.Getenv("KAFKA_BOOTSTRAP_SERVERS")}

	if len(servers) == 0 {
		return nil, modules.ErrMissingKafkaBootstrap // create this error in modules
	}

	return modules.NewKafkaClient(servers)
}

type eventRouteResponse struct {
	Status    string `json:"status"`
	EventID   string `json:"eventId,omitempty"`
	Topic     string `json:"topic,omitempty"`
	Error     string `json:"error,omitempty"`
	Timestamp string `json:"timestamp"`
}

func writeJSON(w http.ResponseWriter, code int, resp eventRouteResponse) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(resp)
}

func EventRouteHandler(w http.ResponseWriter, r *http.Request) {
	start := time.Now()

	// Method guard
	if r.Method != http.MethodPost {
		log.Printf("[ROUTE][EVENT][WARN] method_not_allowed method=%s path=%s\n", r.Method, r.URL.Path)
		writeJSON(w, http.StatusMethodNotAllowed, eventRouteResponse{
			Status:    "error",
			Error:     "method not allowed",
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	if r.Body == nil {
		log.Printf("[ROUTE][EVENT][ERROR] empty_body path=%s\n", r.URL.Path)
		writeJSON(w, http.StatusBadRequest, eventRouteResponse{
			Status:    "error",
			Error:     "empty body",
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	log.Printf("[ROUTE][EVENT] request_received path=%s remote=%s\n", r.URL.Path, r.RemoteAddr)

	// Parse + validate event
	ev, err := modules.BuildEventFromHttp(r)
	if err != nil {
		log.Printf("[ROUTE][EVENT][ERROR] build_event_failed err=%v path=%s\n", err, r.URL.Path)
		writeJSON(w, http.StatusBadRequest, eventRouteResponse{
			Status:    "error",
			Error:     err.Error(),
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	// Kafka client (singleton)
	kc, err := getKafkaClient()
	if err != nil {
		log.Printf("[ROUTE][EVENT][ERROR] kafka_client_init_failed err=%v\n", err)
		writeJSON(w, http.StatusInternalServerError, eventRouteResponse{
			Status:    "error",
			Error:     "kafka init failed",
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	// Produce (use your wrapper so it’s consistent)
	log.Printf("[ROUTE][EVENT] producing id=%s topic=%s source=%s target=%s\n",
		ev.Id, ev.Name, ev.Source, ev.Target,
	)

	if err := kc.SendTopic(ev); err != nil {
		log.Printf("[ROUTE][EVENT][ERROR] produce_failed id=%s topic=%s err=%v\n", ev.Id, ev.Name, err)
		writeJSON(w, http.StatusBadGateway, eventRouteResponse{
			Status:    "error",
			Error:     "kafka produce failed",
			EventID:   ev.Id,
			Topic:     ev.Name,
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	// Flush briefly so HTTP client gets a meaningful success (optional but useful for routers)
	kc.Producer.Flush(2000)

	log.Printf("[ROUTE][EVENT] ok id=%s topic=%s latency_ms=%d\n",
		ev.Id, ev.Name, time.Since(start).Milliseconds(),
	)

	writeJSON(w, http.StatusAccepted, eventRouteResponse{
		Status:    "ok",
		EventID:   ev.Id,
		Topic:     ev.Name,
		Timestamp: time.Now().Format(time.RFC3339Nano),
	})
}
