#!/usr/bin/env python3

from sys import argv, exit
from os import _exit
import json
import asyncio
from aiokafka import AIOKafkaProducer
from aiokafka import AIOKafkaConsumer

local_name = 'init-client'

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

async def insert (insert_clause=None, delete_clause=None, where_clause=None):
    insert_part = 'INSERT {\n'+insert_clause+'\n}\n' if insert_clause else ''
    delete_part = 'DELETE {\n'+delete_clause+'\n}\n' if delete_clause else ''
    where_part  = where_clause if where_clause else ''
    
    update = '''
    PREFIX brick: <http://buildsys.org/ontologies/Brick#>
    PREFIX bf:    <http://buildsys.org/ontologies/BrickFrame#>
    PREFIX bdk:   <https://brickschema.org/schema/1.0.1/BrickDataKafka#>
    PREFIX test:  <http://sdu.dk/ontologies/delme#>
    
    %s
    %s
    WHERE {
        %s
    }
    ''' % (insert_part, delete_part, where_part)
    question = {
        'update': update,
    }
    result = await transcieve(local_name, 'update', question)
    
    return result

async def main ():
    await init()
    
    Building = 'brick:Building'
    Floor    = 'brick:Floor'
    Room     = 'brick:Room'
    Lamp     = 'brick:Lamp'
    Meter    = 'brick:Meter'
    
    contains         = 'brick:contains'
    feedsElectricity = 'brick:feedsElectricity'
    isa              = 'rdf:type'
    label            = 'rdf:label'
    
    building = ent('building')
    floor1   = ent('floor1')
    floor2   = ent('floor2')
    room1    = ent('room1')
    room2    = ent('room2')
    lamp1    = ent('lamp1')
    lamp2    = ent('lamp2')
    meter1   = ent('meter1')
    meter2   = ent('meter2')
    meter3   = ent('meter_main')
    
    triples = [
        (building, isa , Building),
        (floor1, isa , Floor),
        (floor2, isa , Floor),
        (room1, isa , Room),
        (room2, isa , Room),
        (lamp1, isa , Lamp),
        (lamp2, isa , Lamp),
        (meter1, isa , Meter),
        (meter2, isa , Meter),
        (meter3, isa , Meter),
        (building, contains, floor1),
        (building, contains, floor2),
        (floor1, contains, room1),
        (floor2, contains, room2),
        (room1, contains, lamp1),
        (room2, contains, lamp2),
        (room1, label, '"room1"'),
        (room2, label, '"room2"'),
        (meter3, feedsElectricity, meter1),
        (meter3, feedsElectricity, meter2),
        (meter1, feedsElectricity, lamp1),
        (meter2, feedsElectricity, lamp2),
        (meter1, label, '"meter1"'),
        (meter2, label, '"meter2"'),
#        (meter3, label, '"meter3"'),
    ]
    
    for triple in triples:
        result = await insert('%s %s %s' % (triple[0], triple[1], triple[2]))
        print(json.dumps(result, sort_keys=True, indent=4, separators=(',', ': ')))
    
    await finalize()

# guard: command line arguments
if len(argv) != 3:
    print('Syntax: %s BROKER TOPIC_PREFIX' % argv[0])
    print('        %s localhost:9092 rdfserv_topic' % argv[0])
    exit(1)

broker = argv[1]
prefix = argv[2]

loop = asyncio.get_event_loop()

# enter service loop
try:
    loop.run_until_complete(main())
except KeyboardInterrupt:
    print("Exiting ...")
    loop.run_until_complete(finalize())
    loop.close()
    exit(1)

