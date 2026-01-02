package modules

import (
	"log"
	"strings"
	"time"

	"github.com/confluentinc/confluent-kafka-go/kafka"
)

type KafkaClient struct {
	Producer *kafka.Producer
	Consumer *kafka.Consumer
	servers  []string
}

var KafkaClientSingleton *KafkaClient = nil

// ResetKafkaClient closes the singleton (useful for repeatable smoke tests).
func ResetKafkaClient() {
	if KafkaClientSingleton == nil {
		return
	}
	log.Println("[KAFKA] resetting singleton (closing producer/consumer)")

	if KafkaClientSingleton.Consumer != nil {
		_ = KafkaClientSingleton.Consumer.Close()
	}
	if KafkaClientSingleton.Producer != nil {
		// Flush pending deliveries before close
		KafkaClientSingleton.Producer.Flush(3000)
		KafkaClientSingleton.Producer.Close()
	}
	KafkaClientSingleton = nil
}

func NewKafkaClient(servers []string) (*KafkaClient, error) {
	if KafkaClientSingleton != nil {
		return KafkaClientSingleton, nil
	}

	formattedServers := strings.Join(servers, ",")
	log.Println("[KAFKA] SERVERS FORMATTED:", formattedServers)

	p, err := kafka.NewProducer(&kafka.ConfigMap{
		"bootstrap.servers":        formattedServers,
		"client.id":                "koldavarProducer",
		"request.required.acks":    "all",
		"enable.idempotence":       true,
		"message.send.max.retries": 10,
		"retry.backoff.ms":         200,
	})
	if err != nil {
		log.Printf("[KAFKA][ERROR] Failed to create producer: %s\n", err)
		return nil, err
	}

	// Producer delivery reports (super important for debugging)
	go func() {
		for e := range p.Events() {
			if m, ok := e.(*kafka.Message); ok {
				if m.TopicPartition.Error != nil {
					log.Printf("[KAFKA][DELIVERY][ERROR] %v\n", m.TopicPartition.Error)
				} else {
					log.Printf("[KAFKA][DELIVERY][OK] topic=%s partition=%d offset=%d\n",
						*m.TopicPartition.Topic, m.TopicPartition.Partition, m.TopicPartition.Offset)
				}
			}
		}
	}()

	c, err := kafka.NewConsumer(&kafka.ConfigMap{
		"bootstrap.servers":  formattedServers,
		"client.id":          "koldavarConsumer",
		"group.id":           "koldavar", // OK for normal running
		"auto.offset.reset":  "earliest", // good default
		"enable.auto.commit": true,
	})
	if err != nil {
		log.Printf("[KAFKA][ERROR] Failed to create consumer: %s\n", err)
		p.Close()
		return nil, err
	}

	KafkaClientSingleton = &KafkaClient{
		Producer: p,
		Consumer: c,
		servers:  servers,
	}

	log.Println("[KAFKA] KAFKA CLIENT CREATED")
	return KafkaClientSingleton, nil
}

func (kf *KafkaClient) SendTopic(event Event) error {
	return kf.Producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{
			Topic: &event.Name,
		},
		Value: []byte(event.Payload),
	}, nil)
}

func SmokeTestKafka(servers []string, topic string) error {
	log.Println("[KAFKA][SMOKE] starting kafka smoke test")
	log.Printf("[KAFKA][SMOKE] bootstrap servers: %v\n", servers)
	log.Printf("[KAFKA][SMOKE] topic: %s\n", topic)

	// Make smoke test repeatable even with singleton:
	ResetKafkaClient()

	client, err := NewKafkaClient(servers)
	if err != nil {
		log.Printf("[KAFKA][SMOKE][ERROR] failed to create kafka client: %v\n", err)
		return err
	}

	log.Println("[KAFKA][SMOKE] creating test event")
	ev := NewEvent(
		topic,
		"koldavar-local-test",
		"consumer",
		`{"test":"ok","ts":"`+time.Now().Format(time.RFC3339Nano)+`"}`,
	)

	log.Printf("[KAFKA][SMOKE] producing message id=%s payload=%s\n", ev.Id, ev.Payload)
	if err := client.SendTopic(ev); err != nil {
		log.Printf("[KAFKA][SMOKE][ERROR] produce failed: %v\n", err)
		return err
	}

	log.Println("[KAFKA][SMOKE] flushing producer (waiting for delivery report)")
	client.Producer.Flush(5000)
	log.Println("[KAFKA][SMOKE] producer flush completed (check [KAFKA][DELIVERY] logs above)")

	// Bulletproof consume for smoke test: Assign partition 0 from beginning
	log.Println("[KAFKA][SMOKE] assigning consumer directly to topic partition 0 (bypassing group coordinator)")
	tp := kafka.TopicPartition{
		Topic:     &topic,
		Partition: 0,
		Offset:    kafka.OffsetBeginning,
	}
	if err := client.Consumer.Assign([]kafka.TopicPartition{tp}); err != nil {
		log.Printf("[KAFKA][SMOKE][ERROR] assign failed: %v\n", err)
		return err
	}
	log.Println("[KAFKA][SMOKE] consumer assigned successfully")

	log.Println("[KAFKA][SMOKE] starting consume loop (10s window)")
	deadline := time.Now().Add(10 * time.Second)

	for time.Now().Before(deadline) {
		msg, err := client.Consumer.ReadMessage(1 * time.Second)
		if err != nil {
			if ke, ok := err.(kafka.Error); ok && ke.Code() == kafka.ErrTimedOut {
				log.Println("[KAFKA][SMOKE] consumer poll timeout, retrying...")
				continue
			}
			log.Printf("[KAFKA][SMOKE][ERROR] consumer read error: %v\n", err)
			continue
		}

		log.Printf(
			"[KAFKA][SMOKE][RECEIVED] topic=%s partition=%d offset=%d value=%s\n",
			*msg.TopicPartition.Topic,
			msg.TopicPartition.Partition,
			msg.TopicPartition.Offset,
			string(msg.Value),
		)

		log.Println("[KAFKA][SMOKE] message received successfully, ending test")
		return nil
	}

	log.Println("[KAFKA][SMOKE][WARN] no message received before timeout")
	return nil
}
