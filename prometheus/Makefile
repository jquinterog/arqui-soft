run:
	docker run --rm \
		-p 9090:9090 \
		-v ".:/etc/prometheus/" \
		--add-host=host.docker.internal:host-gateway \
		prom/prometheus
