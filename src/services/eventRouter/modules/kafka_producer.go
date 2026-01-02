package modules

import (
	"fmt"
	"log"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

type KafkaProducer struct {
	p *kafka.Producer
}

func NewKafkaProducer(p *kafka.Producer) *KafkaProducer {
	return &KafkaProducer{p: p}
}

func (kp *KafkaProducer) SendEvent(ev Event) error {
	if kp == nil || kp.p == nil {
		return fmt.Errorf("producer is nil")
	}
	return kp.p.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{Topic: &ev.Name},
		Value:          []byte(ev.Payload),
	}, nil)
}

func (kp *KafkaProducer) Flush(ms int) int {
	if kp == nil || kp.p == nil {
		return 0
	}
	return kp.p.Flush(ms)
}

func (kp *KafkaProducer) Close() error {
	if kp == nil || kp.p == nil {
		return nil
	}
	log.Println("[KAFKA] flushing producer before close")
	kp.p.Flush(3000)
	kp.p.Close()
	kp.p = nil
	return nil
}
