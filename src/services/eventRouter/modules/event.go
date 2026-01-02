package modules

import (
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/google/uuid"
)

var (
	ErrInvalidRequest   = errors.New("invalid http request")
	ErrEmptyBody        = errors.New("empty request body")
	ErrMissingEventName = errors.New("missing event name")
	ErrInvalidTopic     = errors.New("invalid kafka topic")

	INPUT_RAW_EXTRACTED = "input.raw.extracted"
	// Input / ingestion
	TOPIC_AUDIO_RAW_EXTRACTED = "audio.raw.extracted"

	// Text synthesis pipeline
	TOPIC_TEXT_SYNTHESIS_INPUT        = "text.synthesis.input"
	TOPIC_TEXT_SYNTHESIS_OUTPUT       = "text.synthesis.output"
	TOPIC_TEXT_GROUP_SYNTHESIS_INPUT  = "text.group.synthesis.input"
	TOPIC_TEXT_GROUP_SYNTHESIS_OUTPUT = "text.group.synthesis.output"

	// Audio synthesis pipeline
	TOPIC_AUDIO_SYNTHESIS_INPUT = "audio.synthesis.input"
	TOPIC_AUDIO_GENERATED       = "audio.generated"

	// Orchestration / infra
	TOPIC_TASK_STATUS  = "task-status"
	TOPIC_PIPELINE_OUT = "pipeline-output"
	TOPIC_DEAD_LETTER  = "dead-letter"
)

type Event struct {
	Name      string
	Id        string
	Source    string
	Target    string
	Payload   string
	Timestamp time.Time
}

func NewEvent(name string, source string, target string, payload string) Event {
	return Event{
		Name:      name,
		Id:        uuid.New().String(),
		Source:    source,
		Target:    target,
		Payload:   payload,
		Timestamp: time.Now(),
	}
}

func IsEventValid(e Event) bool {
	topics := strings.Split(os.Getenv("KAFKA_TOPICS"), ",")

	for i := range topics {
		if strings.TrimSpace(topics[i]) == e.Name {
			return true
		}
	}
	return false
}

func BuildEventFromHttp(r *http.Request) (Event, error) {
	if r == nil {
		log.Println("[EVENT][ERROR] http request is nil")
		return Event{}, ErrInvalidRequest
	}

	log.Println("[EVENT] reading request body")
	body, err := io.ReadAll(r.Body)
	if err != nil {
		log.Printf("[EVENT][ERROR] failed to read request body: %v\n", err)
		return Event{}, err
	}
	_ = r.Body.Close()

	if len(strings.TrimSpace(string(body))) == 0 {
		log.Println("[EVENT][ERROR] empty request body")
		return Event{}, ErrEmptyBody
	}

	log.Printf("[EVENT] raw body: %s\n", string(body))

	var raw map[string]any
	if err := json.Unmarshal(body, &raw); err != nil {
		log.Printf("[EVENT][ERROR] invalid JSON body: %v\n", err)
		return Event{}, err
	}

	getString := func(key string) string {
		v, ok := raw[key]
		if !ok || v == nil {
			return ""
		}
		switch t := v.(type) {
		case string:
			return t
		default:
			b, _ := json.Marshal(t)
			return string(b)
		}
	}

	name := getString("name")
	source := getString("source")
	target := getString("target")

	payload := ""
	if v, ok := raw["payload"]; ok && v != nil {
		switch t := v.(type) {
		case string:
			payload = t
		default:
			b, err := json.Marshal(t)
			if err != nil {
				log.Printf("[EVENT][ERROR] payload not JSON serializable: %v\n", err)
				return Event{}, err
			}
			payload = string(b)
		}
	}

	// Header fallbacks (useful for curl / gateway calls)
	if name == "" {
		name = strings.TrimSpace(r.Header.Get("X-Event-Name"))
	}
	if source == "" {
		source = strings.TrimSpace(r.Header.Get("X-Event-Source"))
	}
	if target == "" {
		target = strings.TrimSpace(r.Header.Get("X-Event-Target"))
	}

	if strings.TrimSpace(name) == "" {
		log.Println("[EVENT][ERROR] missing required field: name")
		return Event{}, ErrMissingEventName
	}

	log.Printf(
		"[EVENT] building event name=%s source=%s target=%s\n",
		name, source, target,
	)

	ev := NewEvent(name, source, target, payload)

	log.Printf(
		"[EVENT] event built id=%s topic=%s timestamp=%s\n",
		ev.Id, ev.Name, ev.Timestamp.Format(time.RFC3339Nano),
	)

	if !IsEventValid(ev) {
		log.Printf(
			"[EVENT][ERROR] invalid topic=%s allowed=%s\n",
			ev.Name,
			os.Getenv("KAFKA_TOPICS"),
		)
		return Event{}, ErrInvalidTopic
	}

	ev = *UpdateEventTarget(&ev)

	log.Printf("[EVENT] event validated successfully id=%s\n", ev.Id)
	return ev, nil
}

func UpdateEventTarget(e *Event) *Event {
	switch e.Source {
	case TOPIC_AUDIO_RAW_EXTRACTED:
		e.Target = TOPIC_TEXT_SYNTHESIS_INPUT

	case TOPIC_TEXT_SYNTHESIS_INPUT:
		e.Target = TOPIC_TEXT_SYNTHESIS_OUTPUT

	case TOPIC_TEXT_GROUP_SYNTHESIS_INPUT:
		e.Target = TOPIC_TEXT_GROUP_SYNTHESIS_OUTPUT

	case TOPIC_TEXT_GROUP_SYNTHESIS_OUTPUT:
		e.Target = TOPIC_AUDIO_GENERATED

	case TOPIC_AUDIO_GENERATED:
		e.Target = TOPIC_PIPELINE_OUT

	default:
		e.Target = INPUT_RAW_EXTRACTED
	}

	return e
}
