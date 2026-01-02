// modules/errors.go
package modules

import "errors"

var ErrMissingKafkaBootstrap = errors.New("missing KAFKA_BOOTSTRAP_SERVERS")
