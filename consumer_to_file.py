from confluent_kafka import Consumer, KafkaException
from confluent_kafka.admin import AdminClient
import clickhouse_connect
import json
import time

# Kafka config
BOOTSTRAP_SERVERS = 'localhost:29092'
TOPIC_PREFIX = 'dbserver1.testdb.'

# Connect to Kafka and discover topics
admin = AdminClient({'bootstrap.servers': BOOTSTRAP_SERVERS})
metadata = admin.list_topics(timeout=10)
topics = [t for t in metadata.topics if t.startswith(TOPIC_PREFIX)]
print("Topics detected:", topics)

# Kafka consumer setup
consumer = Consumer({
    'bootstrap.servers': BOOTSTRAP_SERVERS,
    'group.id': 'confluent-dynamic-' + str(int(time.time())),
    'auto.offset.reset': 'earliest'
})
consumer.subscribe(topics)
print("🚀 Subscribed to topics:", topics)

# ClickHouse setup
client = clickhouse_connect.get_client(host='localhost', port=8123)
client.command("CREATE DATABASE IF NOT EXISTS raw")

# Used to track which tables we already created
created_tables = set()

# Primary key fallback detection
PRIMARY_KEY_CANDIDATES = ['id', 'uuid', 'record_id', 'pk', 'employee_id']

def ensure_table(table_name, sample_record):
    if table_name in created_tables:
        return

    # Infer column types
    cols = []
    for k, v in sample_record.items():
        if isinstance(v, int):
            col_type = 'Int64'
        elif isinstance(v, float):
            col_type = 'Float64'
        else:
            col_type = 'String'
        cols.append(f"{k} {col_type}")

    # Detect primary key for ORDER BY
    order_by_col = next((col for col in PRIMARY_KEY_CANDIDATES if col in sample_record), list(sample_record.keys())[0])

    # DDL creation
    ddl = f"""
    CREATE TABLE IF NOT EXISTS raw.{table_name} (
        {', '.join(cols)}
    ) ENGINE = MergeTree()
    ORDER BY {order_by_col}
    """
    client.command(ddl)
    created_tables.add(table_name)
    print(f"Ensured table raw.{table_name} (ORDER BY {order_by_col})")

# Begin consumption
print("📡 Listening to Debezium topics...")

try:
    while True:
        msg = consumer.poll(3.0)
        if msg is None:
            print("⌛ Waiting for message...")
            continue
        if msg.error():
            print("❗ Error:", msg.error())
            continue

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
            record_id = before.get("id") or before.get("uuid")
            if record_id:
                table_full = f"raw.{table}"
                if isinstance(record_id, str):
                    client.command(f"ALTER TABLE {table_full} DELETE WHERE id = '{record_id}'")
                else:
                    client.command(f"ALTER TABLE {table_full} DELETE WHERE id = {record_id}")
                print(f"🗑️ Deleted from {table_full}: {record_id}")

except KeyboardInterrupt:
    print("Interrupted by user")

finally:
    consumer.close()