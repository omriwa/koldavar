package modules

import (
	"fmt"
	"log"
	"os"
	"strings"
	"sync"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

type KafkaConsumerManager struct {
	bootstrap      string
	clientIDPrefix string
	groupIDPrefix  string

	autoOffsetReset  string
	enableAutoCommit bool

	mu        sync.RWMutex
	consumers map[string]*kafka.Consumer // KEY -> consumer
}

func NewKafkaConsumerManager(bootstrap, clientIDPrefix, groupIDPrefix string) *KafkaConsumerManager {
	aor := strings.TrimSpace(os.Getenv("KAFKA_AUTO_OFFSET_RESET"))
	if aor == "" {
		aor = "earliest"
	}
	
	eac := parseBoolEnvDefault("KAFKA_ENABLE_AUTO_COMMIT", false) // default FALSE for router

	return &KafkaConsumerManager{
		bootstrap:        bootstrap,
		clientIDPrefix:   clientIDPrefix,
		groupIDPrefix:    groupIDPrefix,
		autoOffsetReset:  aor,
		enableAutoCommit: eac,
		consumers:        map[string]*kafka.Consumer{},
	}
}

// Ensure creates/returns consumer for KEY (SCREAMING_SNAKE_CASE, e.g. AUDIO_TO_TEXT)
func (cm *KafkaConsumerManager) Ensure(key string) (*kafka.Consumer, error) {
	key = strings.TrimSpace(key)
	if key == "" {
		return nil, fmt.Errorf("consumer key is empty")
	}

	// Fast path
	cm.mu.RLock()
	if c := cm.consumers[key]; c != nil {
		cm.mu.RUnlock()
		return c, nil
	}
	cm.mu.RUnlock()

	keyLower := strings.ToLower(key)
	groupID := fmt.Sprintf("%s.%s", cm.groupIDPrefix, keyLower)
	clientID := fmt.Sprintf("%s-consumer-%s", cm.clientIDPrefix, keyLower)

	cm.mu.Lock()
	defer cm.mu.Unlock()

	// Re-check
	if c := cm.consumers[key]; c != nil {
		return c, nil
	}

	c, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers":  cm.bootstrap,
		"client.id":          clientID,
		"group.id":           groupID,
		"auto.offset.reset":  cm.autoOffsetReset,
		"enable.auto.commit": cm.enableAutoCommit,
	})
	if err != nil {
		return nil, fmt.Errorf("create consumer key=%s: %w", key, err)
	}

	cm.consumers[key] = c
	log.Printf("[KAFKA] consumer created KEY=%s GROUP_ID=%s CLIENT_ID=%s\n", key, groupID, clientID)
	return c, nil
}

func (cm *KafkaConsumerManager) Build(keys []string) (map[string]*kafka.Consumer, error) {
	out := make(map[string]*kafka.Consumer, len(keys))
	for _, k := range keys {
		c, err := cm.Ensure(k)
		if err != nil {
			return nil, err
		}
		out[k] = c
	}
	return out, nil
}

func (cm *KafkaConsumerManager) Close() error {
	// Snapshot outside lock if you want; this is fine small-scale
	cm.mu.Lock()
	defer cm.mu.Unlock()

	for key, c := range cm.consumers {
		if c == nil {
			continue
		}
		log.Printf("[KAFKA] closing consumer KEY=%s\n", key)
		_ = c.Close()
	}
	cm.consumers = map[string]*kafka.Consumer{}
	return nil
}
