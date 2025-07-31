from confluent_kafka import Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient
import clickhouse_connect
import json
import time
import sys

BOOTSTRAP_SERVERS = 'localhost:29092'
TOPIC_PREFIX = 'dbserver1.'

# Discover topics dynamically
admin = AdminClient({'bootstrap.servers': BOOTSTRAP_SERVERS})
metadata = admin.list_topics(timeout=10)
topics = [t for t in metadata.topics if t.startswith(TOPIC_PREFIX)]
print("📡 Topics detected:", topics)
if not topics:
    print(" No matching topics found with prefix:", TOPIC_PREFIX)
    sys.exit(1)  # Exit gracefully
# Consumer setup with committed offsets and retry safety
consumer = Consumer({
    'bootstrap.servers': BOOTSTRAP_SERVERS,
    'group.id': 'clickhouse-loader',
    'auto.offset.reset': 'earliest',  # start from beginning if no committed offset
    'enable.auto.commit': True,
    'auto.commit.interval.ms': 5000
})
consumer.subscribe(topics)
print("Subscribed to topics")

# Connect to ClickHouse
client = clickhouse_connect.get_client(host='localhost', port=8123)
client.command("CREATE DATABASE IF NOT EXISTS raw")

created_tables = set()
PRIMARY_KEY_CANDIDATES = ['uuid', 'id', 'pk', 'record_id', 'employee_id']

def infer_clickhouse_type(value):
    if isinstance(value, bool):
        return 'UInt8'
    elif isinstance(value, int):
        return 'Int64'
    elif isinstance(value, float):
        return 'Float64'
    else:
        return 'String'

def ensure_table(table_name, sample_record):
    if table_name in created_tables:
        return

    cols = []
    for col, val in sample_record.items():
        col_type = infer_clickhouse_type(val)
        cols.append(f"{col} {col_type}")

    order_by = next((k for k in PRIMARY_KEY_CANDIDATES if k in sample_record), list(sample_record.keys())[0])
    ddl = f"""
    CREATE TABLE IF NOT EXISTS raw.{table_name} (
        {', '.join(cols)}
    ) ENGINE = MergeTree()
    ORDER BY {order_by}
    """
    client.command(ddl)
    created_tables.add(table_name)
    print(f"🛠️ Table created: raw.{table_name} ORDER BY {order_by}")

# Start consuming
print("🚀 Starting to consume Debezium messages...")

try:
    while True:
        msg = consumer.poll(3.0)

        if msg is None:
            print("⌛ Waiting for message...")
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            print("Kafka error:", msg.error())
            continue

        try:
            val = json.loads(msg.value().decode('utf-8'))
            payload = val.get("payload", {})
            if not payload:
                continue

            topic_parts = msg.topic().split('.')
            table = topic_parts[-1]
            op = payload.get("op")

            if op in ["c", "r", "u"]:  # insert or update
                after = payload.get("after", {})
                if after:
                    ensure_table(table, after)
                    client.insert(f"raw.{table}", [list(after.values())], column_names=list(after.keys()))
                    print(f" Inserted into raw.{table}: {after}")

            elif op == "d":
                before = payload.get("before", {})
                table_full = f"raw.{table}"
                record_id = None
                for key in PRIMARY_KEY_CANDIDATES:
                    if key in before:
                        record_id = before[key]
                        key_col = key
                        break
                if record_id:
                    if isinstance(record_id, str):
                        client.command(f"ALTER TABLE {table_full} DELETE WHERE {key_col} = '{record_id}'")
                    else:
                        client.command(f"ALTER TABLE {table_full} DELETE WHERE {key_col} = {record_id}")
                    print(f"🗑️ Deleted from {table_full}: {record_id}")

        except Exception as e:
            print("💥 Error processing message:", e)
            print("🧾 Raw message:", msg.value())

except KeyboardInterrupt:
    print("\n👋 Stopping consumer...")

finally:
    consumer.close()
    print("🔒 Consumer closed safely.")