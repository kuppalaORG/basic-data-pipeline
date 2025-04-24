from kafka import KafkaConsumer
import json

# Kafka consumer setup
consumer = KafkaConsumer(
    'dbserver1.testdb.employees',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='latest',
    group_id='test-consumer',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("Waiting for messages...\n")

for msg in consumer:
    print("==== New message received ====")
    print(msg.value)
