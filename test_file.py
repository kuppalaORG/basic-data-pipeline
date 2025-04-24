from kafka import KafkaConsumer

# Create a basic consumer with no decoding
consumer = KafkaConsumer(
    'dbserver1.testdb.employees',
    bootstrap_servers='172.31.14.166:9092',
    auto_offset_reset='earliest',
    group_id='debug-consumer'
)

print("Listening for messages...")

for msg in consumer:
    print("\n=== NEW MESSAGE ===")
    print(f"Raw value: {msg.value}")
    print(f"Topic: {msg.topic}")
    print(f"Partition: {msg.partition}")
    print(f"Offset: {msg.offset}")
