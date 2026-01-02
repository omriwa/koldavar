package modules

import (
	"os"
	"strings"
)

// parseBoolEnvDefault reads an env var and parses common truthy/falsey values.
// If missing/empty/unknown, it returns def.
func parseBoolEnvDefault(key string, def bool) bool {
	v := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	if v == "" {
		return def
	}
	switch v {
	case "1", "true", "yes", "y", "on":
		return true
	case "0", "false", "no", "n", "off":
		return false
	default:
		return def
	}
}
