from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'dbserver1.testdb.employees',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    group_id='debug-consumer',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for msg in consumer:
    print("\n🟢 Received message:")
    print(json.dumps(msg.value, indent=2))