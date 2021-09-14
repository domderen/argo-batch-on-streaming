from asyncio.events import AbstractEventLoop
import json, sys, asyncio

from nats.aio.client import Client as NATS
from stan.aio.client import Client as STAN

OPERATION_NAMESPACE = 'argo-dataflow-system'


def augment_input(input, workflow_name: str):
  input['__key__'] = workflow_name + '/' + input['key']
  return input


async def run(loop: AbstractEventLoop, workflow_name: str, inputs_count: int):
  processed_inputs_count = 0
  all_inputs_processed_future = loop.create_future()
  inputs = []
  for i in range(inputs_count):
    inputs.append(augment_input({
      "key": f"value{i}",
      f"something{i}": f"els{i}"
    }, workflow_name))
  print('Starting execution for', workflow_name)

  # Use borrowed connection for NATS then mount NATS Streaming
  # client on top.
  nc = NATS()
  await nc.connect(servers=["nats://nats:4222"], io_loop=loop, token='testingtokentestingtoken')

  # Start session with NATS Streaming cluster.
  sc = STAN()
  await sc.connect("stan", f"client-{workflow_name}", nats=nc)

  async def message_handler(msg):
    nonlocal processed_inputs_count, all_inputs_processed_future
    print('inside message handler')
    print(msg)
    subject = msg.subject
    reply = msg.reply
    data = msg.data.decode()
    print("Received a message on '{subject} {reply}': {data}".format(
        subject=subject, reply=reply, data=data))
    processed_inputs_count = processed_inputs_count + 1
    if len(processed_inputs_count) == len(inputs):
      all_inputs_processed_future.set_result()

  await sc.subscribe('argo-dataflow-system.pipeline-without-argo-events.stream-output', cb=message_handler)
  await nc.subscribe('argo-dataflow-system.pipeline-without-argo-events.stream-output', cb=message_handler)

  # Synchronous Publisher, does not return until an ack
  # has been received from NATS Streaming.
  for i in inputs:
    msg = json.dumps(i)
    print('Sending input to dataflow', msg)
    await sc.publish(subject="argo-dataflow-system.pipeline-without-argo-events.stream-input", payload=msg.encode('utf-8'))

  # Close NATS Streaming session
  await sc.close()

  # We are using a NATS borrowed connection so we need to close manually.
  await nc.close()

  print('All inputs sent to dataflow, waiting for them to come back.')
  await all_inputs_processed_future
  print('All inputs were processed by dataflow, finishing.')

if __name__ == '__main__':
  print(sys.argv)
  loop = asyncio.get_event_loop()
  loop.run_until_complete(run(loop, sys.argv[1], int(sys.argv[2])))
  loop.close()