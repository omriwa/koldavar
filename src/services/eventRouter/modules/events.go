package modules

import (
	"time"

	"github.com/google/uuid"
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
