package modules

import (
	"context"
	"log"
	"time"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

// StartDeliveryReportLogger drains producer events and logs delivery reports.
// Call once per producer. Stop it by canceling ctx.
func StartDeliveryReportLogger(ctx context.Context, p *kafka.Producer) {
	if p == nil {
		log.Println("[KAFKA][DELIVERY][WARN] producer is nil; delivery logger not started")
		return
	}

	go func() {
		log.Println("[KAFKA][DELIVERY] logger started")

		events := p.Events()
		for {
			select {
			case <-ctx.Done():
				log.Println("[KAFKA][DELIVERY] logger stopped (context canceled)")
				return

			case e, ok := <-events:
				if !ok {
					// Channel closed when producer is closed
					log.Println("[KAFKA][DELIVERY] logger stopped (producer events channel closed)")
					return
				}

				switch ev := e.(type) {
				case *kafka.Message:
					topic := "<nil>"
					if ev.TopicPartition.Topic != nil {
						topic = *ev.TopicPartition.Topic
					}

					if ev.TopicPartition.Error != nil {
						log.Printf(
							"[KAFKA][DELIVERY][ERROR] topic=%s partition=%d offset=%d err=%v\n",
							topic,
							ev.TopicPartition.Partition,
							ev.TopicPartition.Offset,
							ev.TopicPartition.Error,
						)
						continue
					}

					// Timestamp may be zero if not set; still log it
					ts := ev.Timestamp
					if ts.IsZero() {
						ts = time.Now()
					}

					log.Printf(
						"[KAFKA][DELIVERY][OK] topic=%s partition=%d offset=%d ts=%s\n",
						topic,
						ev.TopicPartition.Partition,
						ev.TopicPartition.Offset,
						ts.Format(time.RFC3339Nano),
					)

				case kafka.Error:
					// Producer-level error events can appear here
					log.Printf("[KAFKA][DELIVERY][ERROR] kafka_error code=%v fatal=%v retriable=%v msg=%v\n",
						ev.Code(), ev.IsFatal(), ev.IsRetriable(), ev)

				default:
					// Ignore other event types; uncomment if you want to debug noise
					// log.Printf("[KAFKA][DELIVERY][DEBUG] event=%T\n", ev)
				}
			}
		}
	}()
}
