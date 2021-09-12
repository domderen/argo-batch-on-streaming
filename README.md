# Argo Batch On Streaming

Example repository showing how to run three projects:

- Argo-Workflows
- Argo-Events
- Argo-Dataflow

Together to implement a batch process handling on top of data streaming pipeline. Data pipeline is implemented in Argo-Dataflow. Argo-Workflows has a WorkflowTemplate that defines a workflows that accepts a batch set of inputs (for example 10k records), and then for such input it would:

1) Create an Argo-Events S3 Event Source, that would contain 1 event per input record (10k events in a single EventSource),
2) Create an Argo-Events Sensor, that would contain a single trigger that would only be ran if all events from my event source were triggered. Again, 10k events would need to be sent, for this Sensor to call its trigger. This Sensor would unsuspend the Argo-Workflow that it was created in (this one, created in step 2).
3) Send each input to a Argo-Dataflow’s Pipeline source, for example Kafka topic, so that each input would run through the Dataflow Pipeline. Again, that’s 10k executions of the steps in this pipeline.
4) Suspend workflow execution, until it will be unsuspended by the Argo-Events Sensor trigger, after all dataflow inputs has been processed.
5) After all my input events are processed by dataflow, I would like to continue this Argo-Workflow to work on a batch of inputs, and treat them as a single package. For example export them as a zip somewhere.

At this point, workflow would delete the Event Source & Sensor, since they served their purpose and are no longer needed.

## Cluster setup

```bash
# Create k3d default cluster to run setup from this repo.
k3d cluster create
# Use k3d's default cluster config
k3d kubeconfig merge -d -s
# Build Docker image(s) used by this system
docker buildx build ./docker_images/send-messages-to-workflow --tag send-messages-to-workflow:1 --load
k3d image import send-messages-to-workflow:1
# Apply kustomization files that install Argo-Dataflow, Argo-Workflows & Argo-Events
kubectl apply -k manifests/argo
# Wait for Kafka Input Pump to be up & running
kubectl -n argo-dataflow-system wait --for=condition=Ready --timeout=300s pod/input
# Apply kustomization files that create Argo-Dataflow Pipeline, Argo-Events EventBus, Argo-Workflows WorkflowTemplate & S3 Bucket initialization job
kubectl apply -k manifests/custom-objects
# Wait for S3 bucket to be created
kubectl -n argo-dataflow-system wait --for=condition=Complete --timeout=60s job/initialize-s3-bucket
# View Argo UI
kubectl -n argo-dataflow-system port-forward svc/argo-server 2746:2746
# IN A NEW TERMINAL: Install Kafka-UI
helm repo add kafka-ui https://provectus.github.io/kafka-ui
helm -n argo-dataflow-system upgrade -i kafka-ui kafka-ui/kafka-ui --set envs.config.KAFKA_CLUSTERS_0_NAME=kafka-broker --set envs.config.KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS=kafka-broker:9092
# Wait for Kafka-UI to be ready
kubectl -n argo-dataflow-system wait --for=condition=Ready --timeout=300s pod -l app.kubernetes.io/name=kafka-ui
# View Kafka-UI
kubectl -n argo-dataflow-system port-forward svc/kafka-ui 8080:80
# IN A NEW TERMINAL: Open Argo-Server UI & Kafka UI
open http://localhost:2746
open http://localhost:8080
```

## Cluster teardown

```bash
k3d cluster delete
```
