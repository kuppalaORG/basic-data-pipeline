from kafka import KafkaConsumer
import json
import os

TOPIC_NAME = "dbserver1.testdb.employees"
BOOTSTRAP_SERVERS = "localhost:9092"
OUTPUT_FILE = "cdc_output.jsonl"

# Create output file if it doesn't exist
if not os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, "w") as f:
        pass

consumer = KafkaConsumer(
    TOPIC_NAME,
    bootstrap_servers=BOOTSTRAP_SERVERS,
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='cdc-to-s3-group',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print(f"📥 Listening to topic: {TOPIC_NAME}... Writing to {OUTPUT_FILE}")

try:
    for message in consumer:
        with open(OUTPUT_FILE, "a") as f:
            json.dump(message.value, f)
            f.write("\n")
        print("✔ Message written to file.")
except KeyboardInterrupt:
    print("\n🛑 Stopped by user.")
finally:
    consumer.close()
