package orders

// Settings is resolved at the composition boundary and supplied explicitly.
type Settings struct {
	DatabaseURL string
}

// Service receives its configuration through the constructor.
type Service struct {
	settings Settings
}

// New constructs the service with explicit settings.
func New(settings Settings) Service {
	return Service{settings: settings}
}

// DatabaseURL returns the supplied configuration value.
func (service Service) DatabaseURL() string {
	return service.settings.DatabaseURL
}
