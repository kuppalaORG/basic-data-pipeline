import json
import re
import time
from kafka import KafkaConsumer
import clickhouse_connect

# ✅ ClickHouse connection (assumes running on host EC2)
client = clickhouse_connect.get_client(host='localhost', port=8123)

# ✅ Kafka consumer setup
# consumer = KafkaConsumer(
#     bootstrap_servers='localhost:9092',
#     auto_offset_reset='earliest',
#     group_id='clickhouse-consumer-test-01',
#     enable_auto_commit=True,
#     value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None
# )

consumer = KafkaConsumer(
    bootstrap_servers='localhost:9092',   # change if needed
    group_id='debug-connection-test',
    auto_offset_reset='earliest',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    consumer_timeout_ms=5000              # exit after timeout
)

print("✅ Connected to Kafka broker.")

# List topics from broker
topics = consumer.topics()
print(f"📌 Available topics: {topics}")

# Describe partitions for your topic (optional)
topic = 'dbserver1.testdb.employees'
if topic in topics:
    partitions = consumer.partitions_for_topic(topic)
    print(f"🧩 Partitions for topic '{topic}': {partitions}")
else:
    print(f"❌ Topic '{topic}' not found on broker.")

for message in consumer:
    print("Received:", message.value)


consumer.subscribe(pattern=re.compile(r'^dbserver1\.testdb\..*'))

# ✅ Keep track of created tables
created_tables = set()

def ensure_table(table_name, sample_record):
    if table_name in created_tables:
        return
    cols = []
    for k, v in sample_record.items():
        if k == 'id':
            col_type = 'Int64'
        elif isinstance(v, float):
            col_type = 'Float64'
        elif isinstance(v, int):
            col_type = 'Int64'
        else:
            col_type = 'String'
        cols.append(f"{k} {col_type}")

    ddl = f"""
    CREATE TABLE IF NOT EXISTS raw.{table_name} (
        {', '.join(cols)}
    ) ENGINE = MergeTree()
    ORDER BY id
    """
    client.command(ddl)
    created_tables.add(table_name)
    print(f"🛠️ Ensured table raw.{table_name}")

print("🚀 Listening to Debezium topics...")

# ✅ Main consume loop
for message in consumer:
    print("Raw Kafka message:", message.value)
    topic = message.topic
    table = topic.split('.')[-1]

    payload = message.value.get("payload")
    if not payload:
        continue

    op = payload.get("op")
    if op in ["c", "u", "r"]:  # create, update, snapshot read
        after = payload.get("after", {})
        if after:
            ensure_table(table, after)
            values = [[after[k] for k in after]]
            client.insert(f"raw.{table}", values, column_names=list(after.keys()))
            print(f"✅ Inserted into raw.{table}: {after}")

    elif op == "d":
        before = payload.get("before", {})
        if before:
            record_id = before.get("id")
            if record_id is not None:
                client.command(f"ALTER TABLE raw.{table} DELETE WHERE id = {int(record_id)}")
                print(f"🗑️ Deleted from raw.{table}: {record_id}")
