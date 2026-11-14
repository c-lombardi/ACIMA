package main

import (
	"flag"
	"os"
)

func main() {
	_ = os.Getenv("ORDERS_DATABASE_URL")
	_ = os.Args
	_ = flag.String("orders-url", "", "orders database URL")
	flag.Parse()
}
