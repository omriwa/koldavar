package modules

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

type KafkaClient struct {
	bootstrap string

	clientIDPrefix string
	groupIDPrefix  string

	ctx    context.Context
	cancel context.CancelFunc

	Producer  *KafkaProducer
	Consumers *KafkaConsumerManager

	mu     sync.Mutex
	closed bool
}

var KafkaClientSingleton *KafkaClient

func ResetKafkaClient() {
	if KafkaClientSingleton == nil {
		return
	}
	log.Println("[KAFKA] resetting singleton (closing producer/consumers)")
	_ = KafkaClientSingleton.Close()
	KafkaClientSingleton = nil
}

func NewKafkaClientFromEnv() (*KafkaClient, error) {
	if KafkaClientSingleton != nil {
		return KafkaClientSingleton, nil
	}

	bootstrap := strings.TrimSpace(os.Getenv("KAFKA_BOOTSTRAP_SERVERS"))
	if bootstrap == "" {
		return nil, ErrMissingKafkaBootstrap
	}
	return newKafkaClient(bootstrap)
}

func NewKafkaClient(servers []string) (*KafkaClient, error) {
	if KafkaClientSingleton != nil {
		return KafkaClientSingleton, nil
	}
	bootstrap := strings.Join(servers, ",")
	if strings.TrimSpace(bootstrap) == "" {
		return nil, ErrMissingKafkaBootstrap
	}
	return newKafkaClient(bootstrap)
}

func newKafkaClient(bootstrap string) (*KafkaClient, error) {
	clientIDPrefix := strings.TrimSpace(os.Getenv("KAFKA_CLIENT_ID_PREFIX"))
	if clientIDPrefix == "" {
		clientIDPrefix = "koldavar"
	}
	groupIDPrefix := strings.TrimSpace(os.Getenv("KAFKA_GROUP_ID_PREFIX"))
	if groupIDPrefix == "" {
		groupIDPrefix = "koldavar"
	}

	log.Printf("[KAFKA] BOOTSTRAP=%s CLIENT_ID_PREFIX=%s GROUP_ID_PREFIX=%s\n",
		bootstrap, clientIDPrefix, groupIDPrefix)

	ctx, cancel := context.WithCancel(context.Background())

	// Producer
	rawProducer, err := kafka.NewProducer(&kafka.ConfigMap{
		"bootstrap.servers":        bootstrap,
		"client.id":                fmt.Sprintf("%s-producer", clientIDPrefix),
		"request.required.acks":    "all",
		"enable.idempotence":       true,
		"message.send.max.retries": 10,
		"retry.backoff.ms":         200,
	})
	if err != nil {
		cancel()
		return nil, fmt.Errorf("create producer: %w", err)
	}

	// Start delivery report logger (stops via ctx cancel OR producer close)
	StartDeliveryReportLogger(ctx, rawProducer)

	kc := &KafkaClient{
		bootstrap:      bootstrap,
		clientIDPrefix: clientIDPrefix,
		groupIDPrefix:  groupIDPrefix,
		ctx:            ctx,
		cancel:         cancel,
	}

	kc.Producer = NewKafkaProducer(rawProducer)
	kc.Consumers = NewKafkaConsumerManager(bootstrap, clientIDPrefix, groupIDPrefix)

	KafkaClientSingleton = kc
	log.Println("[KAFKA] CLIENT CREATED")
	return kc, nil
}

func (kc *KafkaClient) Close() error {
	kc.mu.Lock()
	if kc.closed {
		kc.mu.Unlock()
		return nil
	}
	kc.closed = true

	cancel := kc.cancel
	producer := kc.Producer
	consumers := kc.Consumers
	kc.cancel = nil
	kc.Producer = nil
	kc.Consumers = nil
	kc.mu.Unlock()

	// Stop delivery logger first
	if cancel != nil {
		cancel()
	}

	// Close consumers
	if consumers != nil {
		_ = consumers.Close()
	}

	// Close producer
	if producer != nil {
		_ = producer.Close()
	}

	return nil
}
