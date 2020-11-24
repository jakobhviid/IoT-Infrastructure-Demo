#!/usr/bin/env python3

from sys import argv, exit
from os import _exit
import json
import asyncio
from aiokafka import AIOKafkaProducer
from aiokafka import AIOKafkaConsumer

local_name = 'simulate-mainmeter-client'
SLEEP_TIME = 60

current = {}

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
    await producer.send_and_wait(topic, bytes(json.dumps(value).encode('utf-8')))

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

async def consume (submeter_topic, mainmeter_topic):
    consumer = AIOKafkaConsumer(submeter_topic, loop=loop, bootstrap_servers=broker)
    await consumer.start()
    
    async for msg in consumer:
        current[submeter_topic] = json.loads(msg.value.decode('utf-8'))
        
        s = sum(map(lambda key: current[key], current.keys()))
        c = '[%s]' % ' '.join(map(lambda key: str(current[key]), current.keys()))
        print('%s <- %s (%s) %s' % (mainmeter_topic, s, submeter_topic, c))
        await transmit(mainmeter_topic, s)
    
    await consumer.stop()

async def main ():
    await init()
    
    where_clause = '''
        ?submeter  rdf:type/rdfs:subClassOf* brick:Meter .
        ?mainmeter rdf:type/rdfs:subClassOf* brick:Meter .
        
        ?mainmeter brick:feedsElectricity ?submeter .
        
        ?submeter  rdf:label ?sublabel .
        OPTIONAL { ?mainmeter rdf:label ?mainlabel . } .
    '''
    result = await query('?mainlabel ?sublabel', where_clause)
    print(json.dumps(result, sort_keys=True, indent=4, separators=(',', ': ')))
    
    mains = []
    for row in result['results']:
        mainmeter = row[0]
        if not mainmeter in mains: mains.append(mainmeter)
    
    print('Found %d matches' % len(mains))
    mainmeter = mains[0]
    print('Using "%s"' % mainmeter)
    
    for row in result['results']:
        if row[0] != mainmeter: continue
        submeter = row[1]
        current[submeter] = 0
        asyncio.create_task(consume(submeter, mainmeter))
    
    while True:
        await asyncio.sleep(SLEEP_TIME)
    
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

