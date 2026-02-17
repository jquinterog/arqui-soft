# Kubernetes Setup (Minikube)

This folder contains a local Kubernetes setup with these components:

1. `api-gateway`: entrypoint for the cluster (NGINX, NodePort)
2. `orders-manager-python`: FastAPI service behind the gateway
3. `dynamodb`: local DynamoDB pod (for later integration)
4. `kafka`: Kafka pod for asynchronous messaging (for later integration)

## Manifest Plan

- `namespace.yaml`: dedicated namespace (`arquisoft`)
- `orders-manager-python.yaml`: Deployment + ClusterIP Service for the API
- `api-gateway.yaml`: ConfigMap + Deployment + NodePort Service for ingress traffic
- `dynamodb.yaml`: Deployment + ClusterIP Service for DynamoDB Local
- `kafka.yaml`: Deployment + ClusterIP Service for messaging broker

## Prerequisites

- Minikube installed and running
- `kubectl` configured for Minikube
- Docker available

## 1) Start Minikube

```bash
minikube start
kubectl config use-context minikube
```

## 2) Build the app image and load it into Minikube

Run from repository root:

```bash
docker build -t orders-manager-python:dev ./orders-manager-python
minikube image load orders-manager-python:dev
```

Why this step matters: the deployment uses `imagePullPolicy: IfNotPresent`, so Kubernetes will use the local image you just built.

## 3) Deploy everything

```bash
kubectl apply -f k8s/namespace.yaml
kubectl wait --for=jsonpath='{.status.phase}'=Active namespace/arquisoft --timeout=60s
kubectl apply -f k8s/orders-manager-python.yaml
kubectl apply -f k8s/dynamodb.yaml
kubectl apply -f k8s/kafka.yaml
kubectl apply -f k8s/api-gateway.yaml
```

Avoid running only `kubectl apply -f k8s/` on a fresh cluster, because namespace creation and namespaced resources can race.
If you still prefer one command, run this instead:

```bash
kubectl apply -f k8s/namespace.yaml && \
kubectl wait --for=jsonpath='{.status.phase}'=Active namespace/arquisoft --timeout=60s && \
kubectl apply -f k8s/
```

## 4) Validate deployment

```bash
kubectl get pods -n arquisoft
kubectl get svc -n arquisoft
```

Wait until all pods are `Running` and `READY 1/1`.

## 5) Test through API gateway

Get gateway URL:

```bash
minikube service api-gateway -n arquisoft --url
```

Then test:

```bash
curl "$(minikube service api-gateway -n arquisoft --url)/health"
curl "$(minikube service api-gateway -n arquisoft --url)/orders/health"
curl "$(minikube service api-gateway -n arquisoft --url)/orders/"
```

Expected responses:

- `/health` -> `{"status":"OK"}`
- `/orders/health` -> `{"status":"OK"}`
- `/orders/` -> `welcome`

## 6) Access supporting services (optional checks)

DynamoDB local:

```bash
kubectl port-forward -n arquisoft svc/dynamodb 8000:8000
```

Kafka (local check):

```bash
kubectl port-forward -n arquisoft svc/kafka 9092:9092
```

Then connect from a local Kafka client to `localhost:9092`.

## 7) Update `orders-manager-python` image after code changes

When you change the Python service, rebuild the image, load it into Minikube, and restart the deployment.

Run from repository root:

```bash
docker build -t orders-manager-python:dev ./orders-manager-python
minikube image load orders-manager-python:dev
kubectl rollout restart deployment/orders-manager-python -n arquisoft
kubectl rollout status deployment/orders-manager-python -n arquisoft
```

Alternative (recommended for traceability): use versioned tags.

```bash
docker build -t orders-manager-python:v2 ./orders-manager-python
minikube image load orders-manager-python:v2
kubectl set image deployment/orders-manager-python orders-manager-python=orders-manager-python:v2 -n arquisoft
kubectl rollout status deployment/orders-manager-python -n arquisoft
```

## 8) Cleanup

```bash
kubectl delete namespace arquisoft
```

## Notes

- This setup is for local development on Minikube.
- Kafka is configured as a single-node local broker (KRaft mode).
- No persistent volumes are configured yet; data is ephemeral.
