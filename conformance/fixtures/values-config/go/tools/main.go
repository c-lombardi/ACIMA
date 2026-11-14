package main

import (
	"flag"
	"os"
)

func main() {
	_ = os.Args
	_ = flag.String("config", "acima.config.json", "configuration path")
	flag.Parse()
}
