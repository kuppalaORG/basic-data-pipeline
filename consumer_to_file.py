from confluent_kafka import Consumer, KafkaException, KafkaError
from confluent_kafka.admin import AdminClient
import clickhouse_connect
import json
import time

# Kafka settings
BOOTSTRAP_SERVERS = 'localhost:29092'
VALID_PREFIXES = ['config.', 'sourcing.']

# Discover topics
admin = AdminClient({'bootstrap.servers': BOOTSTRAP_SERVERS})
metadata = admin.list_topics(timeout=10)
topics = [t for t in metadata.topics if any(t.startswith(p) for p in VALID_PREFIXES)]

if not topics:
    print(" No matching topics found with prefix:", VALID_PREFIXES)
    exit(1)

print("📡 Topics detected:", topics)

# Kafka consumer
consumer = Consumer({
    'bootstrap.servers': BOOTSTRAP_SERVERS,
    'group.id': 'clickhouse-dynamic-' + str(int(time.time())),
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': True,
})
consumer.subscribe(topics)
print("Subscribed to topics")

# ClickHouse client
client = clickhouse_connect.get_client(host='localhost', port=8123)
client.command("CREATE DATABASE IF NOT EXISTS raw")

created_tables = set()
PRIMARY_KEY_CANDIDATES = ['uuid', 'id', 'pk', 'employee_id', 'record_id']

def ensure_table(table_name, sample_record):
    if table_name in created_tables:
        return

    cols = []
    for k, v in sample_record.items():
        if isinstance(v, int):
            col_type = 'Int64'
        elif isinstance(v, float):
            col_type = 'Float64'
        elif isinstance(v, bool):
            col_type = 'UInt8'
        else:
            col_type = 'String'
        cols.append(f"{k} {col_type}")

    order_by = next((key for key in PRIMARY_KEY_CANDIDATES if key in sample_record), list(sample_record.keys())[0])
    ddl = f"""
    CREATE TABLE IF NOT EXISTS raw.{table_name} (
        {', '.join(cols)}
    ) ENGINE = MergeTree()
    ORDER BY {order_by}
    """
    client.command(ddl)
    created_tables.add(table_name)
    print(f" Ensured table raw.{table_name} with ORDER BY {order_by}")

# Start consuming
print("🚀 Listening to Debezium topics...")

try:
    while True:
        msg = consumer.poll(3.0)
        if msg is None:
            print("⌛ Waiting for message...")
            continue
        if msg.error():
            print("❗ Kafka error:", msg.error())
            continue

        try:
            val = json.loads(msg.value().decode('utf-8'))
            payload = val.get("payload")
            if not payload:
                continue

            table = msg.topic().split('.')[-1]
            op = payload.get("op")

            if op in ["c", "u", "r"]:
                after = payload.get("after", {})
                if after:
                    ensure_table(table, after)
                    client.insert(f"raw.{table}", [list(after.values())], column_names=list(after.keys()))
                    print(f"📥 Inserted into raw.{table}: {after}")

            elif op == "d":
                before = payload.get("before", {})
                record_id = before.get("uuid") or before.get("id")
                if record_id:
                    where_clause = f"id = '{record_id}'" if isinstance(record_id, str) else f"id = {record_id}"
                    client.command(f"ALTER TABLE raw.{table} DELETE WHERE {where_clause}")
                    print(f"🗑️ Deleted from raw.{table}: {record_id}")

        except Exception as e:
            print("⚠ Error during message handling:", e)

except KeyboardInterrupt:
    print("Interrupted by user")

finally:
    consumer.close()
    print(" Consumer closed")