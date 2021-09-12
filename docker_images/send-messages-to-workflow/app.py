from asyncio.events import AbstractEventLoop
import json, sys, time
import asyncio

from nats.aio.client import Client as NATS
from stan.aio.client import Client as STAN
from kubernetes import client, config

OPERATION_NAMESPACE = 'argo-dataflow-system'

print('Loading kubernetes config')
# Configs can be set in Configuration class directly or using helper utility
config.load_incluster_config()

print('Creating API')
api = client.CustomObjectsApi()


def augment_input(input, workflow_name):
  input['__key__'] = workflow_name + '.' + input['key']
  return input


async def run(loop: AbstractEventLoop, workflow_name: str, inputs_count: int):
  inputs = []
  for i in range(inputs_count):
    inputs.append(augment_input({
      "key": f"value{i}",
      f"something{i}": f"els{i}"
    }, workflow_name))
  print('Starting execution for', workflow_name)
  event_source_name = f"wait-for-events-{workflow_name}-es"
  sensor_name = f"unsuspend-workflow-{workflow_name}-s"

  event_source = {
    "apiVersion": "argoproj.io/v1alpha1",
    "kind": "EventSource",
    "metadata": {
      "name": event_source_name
    },
    "spec": {
      "kafka": {}
    }
  }

  sensor = {
    "apiVersion": "argoproj.io/v1alpha1",
    "kind": "Sensor",
    "metadata": {
      "name": sensor_name
    },
    "spec": {
      "template": {
        "serviceAccountName": "operateworkflow"
      },
      "dependencies": [],
      "triggers": [{
        "template": {
          "name": "unsuspend-workflow",
          "http": {
            "url": f"http://argo-server:2746/api/v1/workflows/{OPERATION_NAMESPACE}/{workflow_name}/resume",
            "method": "PUT"
          }
        },
        "retryStrategy": {
          "steps": 3,
          "duration": "3s"
        }
      }]
    }
  }

  for i, input in enumerate(inputs):
    event_name = f"event-{input['__key__']}"

    # Build Event Source
    event_source_event_obj = {
      "url": "kafka-broker:9092",
      "topic": "stream-output",
      "jsonBody": True,
      "consumerGroup": {
        "groupName": f"event-source-consumer-group-{input['__key__']}",
        "oldest": False,
        "rebalanceStrategy": "range"
      }
    }
    event_source["spec"]["kafka"][event_name] = event_source_event_obj
    
    # Build Sensor
    dependency_obj = {
      "name": f"test-dep-kafka-{i}",
      "eventSourceName": event_source_name,
      "eventName": event_name,
      "filters": {
        "data": [
          {
            "path": "body.key",
            "type": "string",
            "value": [input['__key__']]
          }
        ]
      }
    }
    sensor["spec"]["dependencies"].append(dependency_obj)

  # Create Event Source
  event_source_result = api.create_namespaced_custom_object(
    group="argoproj.io",
    version="v1alpha1",
    namespace=OPERATION_NAMESPACE,
    plural="eventsources",
    body=event_source,
  )
  print('Created Event Source', event_source_result['metadata']['name'], json.dumps(event_source_result))

  # Create Sensor
  sensor_result = api.create_namespaced_custom_object(
    group="argoproj.io",
    version="v1alpha1",
    namespace=OPERATION_NAMESPACE,
    plural="sensors",
    body=sensor,
  )
  print('Created Sensor', sensor_result['metadata']['name'], json.dumps(sensor_result))

  print('Waiting for EventSource to be ready')
  while True:
    event_source_result = api.get_namespaced_custom_object(
      group="argoproj.io",
      version="v1alpha1",
      namespace=OPERATION_NAMESPACE,
      plural="eventsources",
      name=event_source_name
    )
    print('Waiting for event source', event_source_result['metadata']['name'])
    if event_source_result.get('status') is not None and event_source_result['status'].get('conditions') is not None and len(event_source_result['status']['conditions']) == 2:
      break
    time.sleep(2)

  print('Waiting for Sensor to be ready')
  while True:
    sensor_result = api.get_namespaced_custom_object(
      group="argoproj.io",
      version="v1alpha1",
      namespace=OPERATION_NAMESPACE,
      plural="sensors",
      name=sensor_name
    )
    print('Waiting for sensor', sensor_result['metadata']['name'])
    if sensor_result.get('status') is not None and sensor_result['status'].get('conditions') is not None and len(sensor_result['status']['conditions']) == 3:
      break
    time.sleep(2)

  # Use borrowed connection for NATS then mount NATS Streaming
  # client on top.
  nc = NATS()
  await nc.connect(servers=["nats://nats:4222"], io_loop=loop, token='testingtokentestingtoken')

  # Start session with NATS Streaming cluster.
  sc = STAN()
  await sc.connect("stan", f"client-{workflow_name}", nats=nc)

  # Synchronous Publisher, does not return until an ack
  # has been received from NATS Streaming.
  for i in inputs:
    msg = json.dumps(i)
    print('Sending input to dataflow', msg)
    await sc.publish(subject="argo-dataflow-system.101-two-node.stream-input", payload=msg.encode('utf-8'))

  # Close NATS Streaming session
  await sc.close()

  # We are using a NATS borrowed connection so we need to close manually.
  await nc.close()

  print('All inputs sent to dataflow, finishing.')

if __name__ == '__main__':
  print(sys.argv)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(run(loop, sys.argv[1], int(sys.argv[2])))
  loop.close()