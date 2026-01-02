package routes

import (
	"encoding/json"
	"eventRouter/main/modules"
	"log"
	"net/http"
	"sync"
	"time"
)

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

var (
	kafkaOnce sync.Once
	kafkaCli  *modules.KafkaClient
	kafkaErr  error
)

func getKafkaClient() (*modules.KafkaClient, error) {
	kafkaOnce.Do(func() {
		kafkaCli, kafkaErr = modules.NewKafkaClientFromEnv()
	})
	return kafkaCli, kafkaErr
}

func EventRouteHandler(w http.ResponseWriter, r *http.Request) {
	start := time.Now()

	if r.Method != http.MethodPost {
		log.Printf("[ROUTE][EVENT][WARN] METHOD_NOT_ALLOWED METHOD=%s PATH=%s\n", r.Method, r.URL.Path)
		writeJSON(w, http.StatusMethodNotAllowed, eventRouteResponse{
			Status:    "error",
			Error:     "method not allowed",
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	if r.Body == nil {
		log.Printf("[ROUTE][EVENT][ERROR] EMPTY_BODY PATH=%s\n", r.URL.Path)
		writeJSON(w, http.StatusBadRequest, eventRouteResponse{
			Status:    "error",
			Error:     "empty body",
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	log.Printf("[ROUTE][EVENT] REQUEST_RECEIVED PATH=%s REMOTE=%s\n", r.URL.Path, r.RemoteAddr)

	ev, err := modules.BuildEventFromHttp(r)
	if err != nil {
		log.Printf("[ROUTE][EVENT][ERROR] BUILD_EVENT_FAILED ERR=%v PATH=%s\n", err, r.URL.Path)
		writeJSON(w, http.StatusBadRequest, eventRouteResponse{
			Status:    "error",
			Error:     err.Error(),
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	kc, err := getKafkaClient()
	if err != nil {
		msg := "kafka init failed"
		if err == modules.ErrMissingKafkaBootstrap {
			msg = "missing KAFKA_BOOTSTRAP_SERVERS"
		}
		log.Printf("[ROUTE][EVENT][ERROR] KAFKA_CLIENT_INIT_FAILED ERR=%v\n", err)
		writeJSON(w, http.StatusInternalServerError, eventRouteResponse{
			Status:    "error",
			Error:     msg,
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	// Producer wrapper (decoupled)
	if kc.Producer == nil {
		log.Printf("[ROUTE][EVENT][ERROR] PRODUCER_NIL\n")
		writeJSON(w, http.StatusInternalServerError, eventRouteResponse{
			Status:    "error",
			Error:     "kafka producer not initialized",
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	log.Printf("[ROUTE][EVENT] PRODUCING ID=%s TOPIC=%s SOURCE=%s TARGET=%s\n",
		ev.Id, ev.Name, ev.Source, ev.Target,
	)

	if err := kc.Producer.SendEvent(ev); err != nil {
		log.Printf("[ROUTE][EVENT][ERROR] PRODUCE_FAILED ID=%s TOPIC=%s ERR=%v\n", ev.Id, ev.Name, err)
		writeJSON(w, http.StatusBadGateway, eventRouteResponse{
			Status:    "error",
			Error:     "kafka produce failed",
			EventID:   ev.Id,
			Topic:     ev.Name,
			Timestamp: time.Now().Format(time.RFC3339Nano),
		})
		return
	}

	// Optional: improve UX; keep short.
	kc.Producer.Flush(2000)

	log.Printf("[ROUTE][EVENT] OK ID=%s TOPIC=%s LATENCY_MS=%d\n",
		ev.Id, ev.Name, time.Since(start).Milliseconds(),
	)

	writeJSON(w, http.StatusAccepted, eventRouteResponse{
		Status:    "ok",
		EventID:   ev.Id,
		Topic:     ev.Name,
		Timestamp: time.Now().Format(time.RFC3339Nano),
	})
}
