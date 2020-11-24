#!/usr/bin/env python3

from sys import argv, exit
from os import _exit
import json
import asyncio
from time import sleep
from aiokafka import AIOKafkaProducer
from aiokafka import AIOKafkaConsumer

local_name = 'simulate-submeter-client'
SLEEP_TIME = 1

def ent (local_name):
    return 'test:%s' % local_name

async def init ():
    global producer
    
    loop = asyncio.get_event_loop()
    
    producer = AIOKafkaProducer(loop=loop, bootstrap_servers=broker)
    await producer.start()

async def finalize ():
    await producer.stop()

async def transcieve (local_name, remote_name, question):
    question['result-path'] = local_name
    topic = '%s_%s' % (prefix, remote_name)
    loop = asyncio.get_event_loop()
    
    consumer = AIOKafkaConsumer(local_name, loop=loop, bootstrap_servers=broker)
    await consumer.start()
    
    await producer.send_and_wait(topic, bytes(json.dumps(question).encode('utf-8')))
    
    async for msg in consumer:
        result = json.loads((msg.value).decode('utf-8'))
        break
    await consumer.stop()
    
    return result

async def transmit (topic, value):
    message = str(value)
    await producer.send_and_wait(topic, bytes(json.dumps(message).encode('utf-8')))

async def query (select_clause, where_clause):
    query = '''
    PREFIX brick: <http://buildsys.org/ontologies/Brick#>
    PREFIX bf:    <http://buildsys.org/ontologies/BrickFrame#>
    PREFIX bdk:   <https://brickschema.org/schema/1.0.1/BrickDataKafka#>
    PREFIX test:  <http://sdu.dk/ontologies/delme#>
    
    SELECT %s
    WHERE {
        %s
    }
    ''' % (select_clause, where_clause)
    question = {
        'query': query,
    }
    result = await transcieve(local_name, 'query', question)
    
    return result

async def main ():
    await init()
    
    where_clause = '''
        ?room  rdf:type/rdfs:subClassOf* brick:Room .
        ?lamp  rdf:type/rdfs:subClassOf* brick:Lamp .
        ?meter rdf:type/rdfs:subClassOf* brick:Meter .
        
        ?room rdf:label "%s" .
        ?room brick:contains ?lamp .
        ?meter brick:feedsElectricity ?lamp .
        ?meter rdf:label ?label
    ''' % room
    result = await query('?label', where_clause)
#    print(json.dumps(result, sort_keys=True, indent=4, separators=(',', ': ')))
    
    print('Found %d matches' % len(result['results']))
    topic = result['results'][0][0]
    print('Using "%s"' % topic)
    
    value = 0
    while True:
        print('%s <- %d' % (topic, value))
        await transmit(topic, value)
        value += 1
        sleep(SLEEP_TIME)
    
    await finalize()

# guard: command line arguments
if len(argv) != 4:
    print('Syntax: %s BROKER TOPIC_PREFIX ROOM_LABEL' % argv[0])
    print('        %s localhost:9092 rdfserv_topic room1' % argv[0])
    exit(1)

broker = argv[1]
prefix = argv[2]
room   = argv[3]

loop = asyncio.get_event_loop()

# enter service loop
try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    print("Exiting ...")
    loop.run_until_complete(finalize())
    loop.close()
    exit(1)

