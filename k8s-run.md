# File to paste the output of commands

```
minikube start
😄  minikube v1.33.1 on Ubuntu 22.04
🎉  minikube 1.38.0 is available! Download it: https://github.com/kubernetes/minikube/releases/tag/v1.38.0
💡  To disable this notice, run: 'minikube config set WantUpdateNotification false'

✨  Automatically selected the docker driver
📌  Using Docker driver with root privileges
👍  Starting "minikube" primary control-plane node in "minikube" cluster
🚜  Pulling base image v0.0.44 ...
💾  Downloading Kubernetes v1.30.0 preload ...
    > preloaded-images-k8s-v18-v1...:  342.90 MiB / 342.90 MiB  100.00% 12.99 M
🔥  Creating docker container (CPUs=2, Memory=3900MB) ...
🐳  Preparing Kubernetes v1.30.0 on Docker 26.1.1 ...
    ▪ Generating certificates and keys ...
    ▪ Booting up control plane ...
    ▪ Configuring RBAC rules ...
🔗  Configuring bridge CNI (Container Networking Interface) ...
🔎  Verifying Kubernetes components...
    ▪ Using image gcr.io/k8s-minikube/storage-provisioner:v5
🌟  Enabled addons: storage-provisioner, default-storageclass

❗  /snap/bin/kubectl is version 1.34.4, which may have incompatibilities with Kubernetes 1.30.0.
    ▪ Want kubectl v1.30.0? Try 'minikube kubectl -- get pods -A'
🏄  Done! kubectl is now configured to use "minikube" cluster and "default" namespace by default
```

```
kubectl config use-context minikube
Switched to context "minikube".
```

```
docker build -t orders-manager-python:dev ./orders-manager-python
[+] Building 12.0s (9/9) FINISHED                                                                                                                         docker:default
 => [internal] load build definition from Dockerfile                                                                                                                0.0s
 => => transferring dockerfile: 178B                                                                                                                                0.0s
 => [internal] load metadata for docker.io/library/python:3.12-slim                                                                                                 1.7s
 => [internal] load .dockerignore                                                                                                                                   0.0s
 => => transferring context: 2B                                                                                                                                     0.0s
 => [1/4] FROM docker.io/library/python:3.12-slim@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab                                           4.7s
 => => resolve docker.io/library/python:3.12-slim@sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab                                           0.0s
 => => sha256:9e01bf1ae5db7649a236da7be1e94ffbbbdd7a93f867dd0d8d5720d9e1f89fab 10.37kB / 10.37kB                                                                    0.0s
 => => sha256:48006ff57afe15f247ad3da166e9487da0f66a94adbc92810b0e189382d79246 1.75kB / 1.75kB                                                                      0.0s
 => => sha256:b3b92273ebb48091c16ef5f9cc1fdde40d18c7365ec38df5e9f900a2aeb3db1c 5.66kB / 5.66kB                                                                      0.0s
 => => sha256:0c8d55a45c0dc58de60579b9cc5b708de9e7957f4591fc7de941b67c7e245da0 29.78MB / 29.78MB                                                                    3.2s
 => => sha256:690eaffcf0e9a6e579bf82062d0d78590bd1bc000a309b8e76ff4ca460bcdb6f 1.29MB / 1.29MB                                                                      0.5s
 => => sha256:9395e1d7be50336f1932db3e6904cc05ad5b727731f03ae218688af3f525ec30 12.11MB / 12.11MB                                                                    1.8s
 => => sha256:4948ee38326639b0ee49566ec9752e0500fde95ffa7a4771067a7856446029fe 251B / 251B                                                                          1.0s
 => => extracting sha256:0c8d55a45c0dc58de60579b9cc5b708de9e7957f4591fc7de941b67c7e245da0                                                                           0.8s
 => => extracting sha256:690eaffcf0e9a6e579bf82062d0d78590bd1bc000a309b8e76ff4ca460bcdb6f                                                                           0.1s
 => => extracting sha256:9395e1d7be50336f1932db3e6904cc05ad5b727731f03ae218688af3f525ec30                                                                           0.4s
 => => extracting sha256:4948ee38326639b0ee49566ec9752e0500fde95ffa7a4771067a7856446029fe                                                                           0.0s
 => [internal] load build context                                                                                                                                   0.0s
 => => transferring context: 11.65kB                                                                                                                                0.0s
 => [2/4] WORKDIR /app                                                                                                                                              0.2s
 => [3/4] COPY . ./                                                                                                                                                 0.0s
 => [4/4] RUN pip install --no-cache-dir -r requirements.txt                                                                                                        5.1s
 => exporting to image                                                                                                                                              0.2s
 => => exporting layers                                                                                                                                             0.2s
 => => writing image sha256:ba510ef6acda6cfbf537ce9dc80b1b5f14f217574284932facce57c372c7001b                                                                        0.0s
 => => naming to docker.io/library/orders-manager-python:dev
```

```
minikube image load orders-manager-python:dev
```

```
kubectl apply -f k8s/
namespace/arquisoft created
deployment.apps/orders-manager-python created
service/orders-manager-python created
Error from server (NotFound): error when creating "k8s/api-gateway.yaml": namespaces "arquisoft" not found
Error from server (NotFound): error when creating "k8s/api-gateway.yaml": namespaces "arquisoft" not found
Error from server (NotFound): error when creating "k8s/api-gateway.yaml": namespaces "arquisoft" not found
Error from server (NotFound): error when creating "k8s/dynamodb.yaml": namespaces "arquisoft" not found
Error from server (NotFound): error when creating "k8s/dynamodb.yaml": namespaces "arquisoft" not found
Error from server (NotFound): error when creating "k8s/kafka.yaml": namespaces "arquisoft" not found
Error from server (NotFound): error when creating "k8s/kafka.yaml": namespaces "arquisoft" not found
```

```
kubectl apply -f k8s/namespace.yaml && \
kubectl wait --for=jsonpath='{.status.phase}'=Active namespace/arquisoft --timeout=60s && \
kubectl apply -f k8s/
namespace/arquisoft unchanged
namespace/arquisoft condition met
configmap/api-gateway-nginx-config created
deployment.apps/api-gateway created
service/api-gateway created
deployment.apps/dynamodb created
service/dynamodb created
deployment.apps/kafka created
service/kafka created
namespace/arquisoft unchanged
deployment.apps/orders-manager-python unchanged
service/orders-manager-python unchanged
```

```
kubectl get pods -n arquisoft
NAME                                     READY   STATUS         RESTARTS   AGE
api-gateway-5d4559d9c9-bwh2v             1/1     Running        0          64s
dynamodb-8587bddc95-67wpn                1/1     Running        0          64s
kafka-6fdc7677cb-w8wbw                   0/1     ErrImagePull   0          64s
orders-manager-python-7c967c4489-n8t8g   1/1     Running        0          5m48s
```

```
kubectl get svc -n arquisoft
NAME                    TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE
api-gateway             NodePort    10.108.44.145    <none>        80:30080/TCP   2m14s
dynamodb                ClusterIP   10.110.15.187    <none>        8000/TCP       2m14s
kafka                   ClusterIP   10.99.201.174    <none>        9092/TCP       2m14s
orders-manager-python   ClusterIP   10.111.118.202   <none>        5000/TCP       6m58s
```

```
minikube service api-gateway -n arquisoft --url
http://192.168.49.2:30080
```

```
curl "$(minikube service api-gateway -n arquisoft --url)/health"
{"status":"OK"}
curl "$(minikube service api-gateway -n arquisoft --url)/orders/health"
{"status":"OK"}
curl "$(minikube service api-gateway -n arquisoft --url)/orders/"
welcome
```
