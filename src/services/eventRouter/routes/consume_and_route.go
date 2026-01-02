package routes

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"eventRouter/main/modules"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

// --- Topic -> ServiceKey routing (NO new env required) ---
const (
	SVC_INPUT_EXTRACTION = "INPUT_EXTRACTION"
	SVC_AUDIO_TO_TEXT    = "AUDIO_TO_TEXT"
	SVC_TEXT_SYNTHESIZER = "TEXT_SYNTHESIZER"
	SVC_SYNC_MANAGER     = "SYNC_MANAGER"
	SVC_TTS              = "TTS"
)

var TopicToServiceKey = map[string]string{
	"input.raw.extracted":        SVC_INPUT_EXTRACTION,
	"audio.raw.extracted":        SVC_AUDIO_TO_TEXT,
	"text.synthesis.input":       SVC_TEXT_SYNTHESIZER,
	"text.group.synthesis.input": SVC_TEXT_SYNTHESIZER,
	"task-status":                SVC_SYNC_MANAGER,
	"pipeline-output":            SVC_SYNC_MANAGER,
	"audio.synthesis.input":      SVC_TTS, // only if TTS enabled (baseurl exists)
}

// --- serviceKey -> baseurl env var ---
var ServiceKeyToBaseURLEnv = map[string]string{
	SVC_INPUT_EXTRACTION: "ROUTER_BASEURL_INPUT_EXTRACTION",
	SVC_AUDIO_TO_TEXT:    "ROUTER_BASEURL_AUDIO_TO_TEXT",
	SVC_TEXT_SYNTHESIZER: "ROUTER_BASEURL_TEXT_SYNTHESIZER",
	SVC_SYNC_MANAGER:     "ROUTER_BASEURL_SYNC_MANAGER",
	SVC_TTS:              "ROUTER_BASEURL_TTS",
}

// default endpoint if not provided
func endpointFor(serviceKey string) string {
	// Optional: allow overriding endpoint via env without adding values.yaml keys
	// Example env: ROUTER_ENDPOINT_TEXT_SYNTHESIZER=/events
	key := "ROUTER_ENDPOINT_" + serviceKey
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return "/"
	}
	return v
}

type dlqEnvelope struct {
	FailedAt     string          `json:"failed_at"`
	Reason       string          `json:"reason"`
	SourceTopic  string          `json:"source_topic"`
	Partition    int32           `json:"partition"`
	Offset       int64           `json:"offset"`
	ServiceKey   string          `json:"service_key"`
	TargetURL    string          `json:"target_url"`
	OriginalKey  []byte          `json:"original_key,omitempty"`
	OriginalBody json.RawMessage `json:"original_body"`
}

func httpClient() *http.Client {
	timeoutMs := intEnv("ROUTER_HTTP_TIMEOUT_MS", 8000)
	return &http.Client{Timeout: time.Duration(timeoutMs) * time.Millisecond}
}

func intEnv(key string, def int) int {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return def
	}
	n, err := strconvAtoiSafe(v)
	if err != nil {
		return def
	}
	return n
}

func strconvAtoiSafe(s string) (int, error) {
	// tiny helper to avoid importing strconv all over
	var n int
	_, err := fmt.Sscanf(s, "%d", &n)
	return n, err
}

func postJSON(ctx context.Context, cli *http.Client, url string, body any) (int, []byte, error) {
	b, err := json.Marshal(body)
	if err != nil {
		return 0, nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := cli.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer resp.Body.Close()

	out, _ := ioReadAllSafe(resp.Body)
	return resp.StatusCode, out, nil
}

func ioReadAllSafe(r io.Reader) ([]byte, error) {
	// minimal io.ReadAll without importing io for older style; but best to import io
	return io.ReadAll(r)
}

// StartKafkaRouting spins up consumer loops per service (group-id isolation).
func StartKafkaRouting(ctx context.Context, kc *modules.KafkaClient) error {
	if kc == nil || kc.Consumers == nil || kc.Producer == nil {
		return errors.New("kafka client not ready (producer/consumers nil)")
	}

	// Build topics per service key
	serviceTopics := map[string][]string{}
	for topic, svcKey := range TopicToServiceKey {
		serviceTopics[svcKey] = append(serviceTopics[svcKey], topic)
	}

	cli := httpClient()
	retries := intEnv("ROUTER_HTTP_RETRIES", 3)
	backoffMs := intEnv("ROUTER_HTTP_RETRY_BACKOFF_MS", 250)

	// Create consumer per serviceKey (if base URL exists)
	for svcKey, topics := range serviceTopics {
		baseEnv := ServiceKeyToBaseURLEnv[svcKey]
		baseURL := strings.TrimSpace(os.Getenv(baseEnv))
		if baseURL == "" {
			log.Printf("[ROUTER][CONSUME][SKIP] SERVICE_KEY=%s missing %s\n", svcKey, baseEnv)
			continue
		}

		consumer, err := kc.Consumers.Ensure(svcKey)
		if err != nil {
			return fmt.Errorf("create consumer %s: %w", svcKey, err)
		}

		// Subscribe this consumer only to its topics
		log.Printf("[ROUTER][CONSUME] SERVICE_KEY=%s SUBSCRIBE=%v\n", svcKey, topics)
		if err := consumer.SubscribeTopics(topics, nil); err != nil {
			return fmt.Errorf("subscribe %s: %w", svcKey, err)
		}

		// Run one loop per serviceKey
		go consumeLoop(ctx, kc, consumer, svcKey, baseURL, endpointFor(svcKey), cli, retries, backoffMs)
	}

	return nil
}

func consumeLoop(
	ctx context.Context,
	kc *modules.KafkaClient,
	consumer *kafka.Consumer,
	serviceKey string,
	baseURL string,
	endpoint string,
	cli *http.Client,
	retries int,
	backoffMs int,
) {
	targetURL := strings.TrimRight(baseURL, "/") + endpoint
	log.Printf("[ROUTER][CONSUME] START SERVICE_KEY=%s TARGET=%s\n", serviceKey, targetURL)

	pollTimeout := time.Duration(intEnv("KAFKA_POLL_TIMEOUT_MS", 1000)) * time.Millisecond

	for {
		select {
		case <-ctx.Done():
			log.Printf("[ROUTER][CONSUME] STOP SERVICE_KEY=%s\n", serviceKey)
			return
		default:
		}

		msg, err := consumer.ReadMessage(pollTimeout)
		if err != nil {
			// ignore poll timeouts
			if ke, ok := err.(kafka.Error); ok && ke.Code() == kafka.ErrTimedOut {
				continue
			}
			log.Printf("[ROUTER][CONSUME][WARN] SERVICE_KEY=%s read_err=%v\n", serviceKey, err)
			continue
		}

		topic := "<nil>"
		if msg.TopicPartition.Topic != nil {
			topic = *msg.TopicPartition.Topic
		}

		// Forward envelope to worker
		workerReq := map[string]any{
			"topic": topic,
			"key":   string(msg.Key),
			"value": json.RawMessage(msg.Value), // keep exact bytes
			"meta": map[string]any{
				"partition": msg.TopicPartition.Partition,
				"offset":    int64(msg.TopicPartition.Offset),
				"ts":        msg.Timestamp.Format(time.RFC3339Nano),
			},
		}

		ok := false
		var lastErr error
		var lastStatus int
		for attempt := 1; attempt <= retries; attempt++ {
			status, body, err := postJSON(ctx, cli, targetURL, workerReq)
			lastStatus = status
			lastErr = err

			if err == nil && status >= 200 && status < 300 {
				ok = true
				break
			}

			log.Printf("[ROUTER][FORWARD][WARN] SERVICE_KEY=%s topic=%s partition=%d offset=%d attempt=%d/%d status=%d err=%v resp=%s\n",
				serviceKey, topic, msg.TopicPartition.Partition, msg.TopicPartition.Offset,
				attempt, retries, status, err, truncate(body, 200),
			)
			time.Sleep(time.Duration(backoffMs) * time.Millisecond)
		}

		if ok {
			// Commit offset ONLY after worker success
			if _, err := consumer.CommitMessage(msg); err != nil {
				log.Printf("[ROUTER][COMMIT][WARN] SERVICE_KEY=%s topic=%s offset=%d err=%v\n",
					serviceKey, topic, msg.TopicPartition.Offset, err)
			} else {
				log.Printf("[ROUTER][OK] SERVICE_KEY=%s topic=%s partition=%d offset=%d\n",
					serviceKey, topic, msg.TopicPartition.Partition, msg.TopicPartition.Offset)
			}
			continue
		}

		// Failed after retries -> DLQ then commit (avoid poison-pill loop)
		reason := fmt.Sprintf("forward_failed status=%d err=%v", lastStatus, lastErr)
		dlq := dlqEnvelope{
			FailedAt:     time.Now().Format(time.RFC3339Nano),
			Reason:       reason,
			SourceTopic:  topic,
			Partition:    msg.TopicPartition.Partition,
			Offset:       int64(msg.TopicPartition.Offset),
			ServiceKey:   serviceKey,
			TargetURL:    targetURL,
			OriginalKey:  msg.Key,
			OriginalBody: json.RawMessage(msg.Value),
		}

		ev := modules.NewEvent(
			"dead-letter",
			"event-router",
			serviceKey,
			mustJSON(dlq),
		)

		if err := kc.Producer.SendEvent(ev); err != nil {
			log.Printf("[ROUTER][DLQ][ERROR] produce_failed topic=%s offset=%d err=%v\n",
				topic, msg.TopicPartition.Offset, err)
			// Do NOT commit if DLQ failed; otherwise you'd lose the message.
			continue
		}
		kc.Producer.Flush(2000)

		// Commit now that DLQ is stored
		if _, err := consumer.CommitMessage(msg); err != nil {
			log.Printf("[ROUTER][COMMIT][WARN] after_dlq SERVICE_KEY=%s topic=%s offset=%d err=%v\n",
				serviceKey, topic, msg.TopicPartition.Offset, err)
		}

		log.Printf("[ROUTER][DLQ][OK] SERVICE_KEY=%s topic=%s partition=%d offset=%d\n",
			serviceKey, topic, msg.TopicPartition.Partition, msg.TopicPartition.Offset)
	}
}

func mustJSON(v any) string {
	b, _ := json.Marshal(v)
	return string(b)
}

func truncate(b []byte, n int) string {
	if len(b) <= n {
		return string(b)
	}
	return string(b[:n]) + "..."
}
