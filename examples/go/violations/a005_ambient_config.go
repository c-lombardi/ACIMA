//go:build ignore

// acima-unit: orders
package orders

import (
	stdflag "flag"
	stdos "os"
)

func DatabaseURL() string {
	return stdos.Getenv("ORDERS_DATABASE_URL")
}

func OptionalToken() (string, bool) {
	return stdos.LookupEnv("ORDERS_API_TOKEN")
}

func Port() int {
	return *stdflag.Int("orders-port", 8080, "orders listen port")
}

func ParseFlags() {
	stdflag.Parse()
}

func Arguments() []string {
	return stdos.Args
}
