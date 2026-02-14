deps:
	go mod vendor && go mod tidy

build: deps
	CGO_ENABLED=0 GOOS=linux go build -o orders-manager

run:
	go run main.go
