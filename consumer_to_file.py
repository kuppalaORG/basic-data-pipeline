from confluent_kafka import Consumer
import json
import time

topic = 'dbserver1.testdb.employees'

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'confluent-test-' + str(int(time.time())),
    'auto.offset.reset': 'earliest'
})

consumer.subscribe([topic])
print("🚀 Subscribed to topic:", topic)

try:
    while True:
        msg = consumer.poll(5.0)
        if msg is None:
            print("⏳ Waiting for message...")
            continue
        if msg.error():
            print("❌ Consumer error:", msg.error())
            continue

        print("\nMessage received:")
        print("Raw:", msg.value())

        try:
            decoded = json.loads(msg.value().decode('utf-8'))
            print("Decoded JSON:", json.dumps(decoded, indent=2))
        except Exception as e:
            print("❌ JSON decode error:", e)

except KeyboardInterrupt:
    print("👋 Exit requested")

finally:
    consumer.close()

# Connect to ClickHouse
client = clickhouse_connect.get_client(host='localhost', port=8123)
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

# Main consumption loop
for message in consumer:
    try:
        print("📨 New Message")
        payload = message.value.get("payload")
        if not payload:
            continue

        op = payload.get("op")
        table = message.topic.split('.')[-1]

        if op in ["c", "u", "r"]:
            after = payload.get("after", {})
            if after:
                ensure_table(table, after)
                values = [[after[k] for k in after]]
                client.insert(f"raw.{table}", values, column_names=list(after.keys()))
                print(f"Inserted into raw.{table}: {after}")

        elif op == "d":
            before = payload.get("before", {})
            if before:
                record_id = before.get("id")
                if record_id is not None:
                    client.command(f"ALTER TABLE raw.{table} DELETE WHERE id = {int(record_id)}")
                    print(f"❌ Deleted from raw.{table}: {record_id}")

    except Exception as e:
        print(f"❌ Error processing message: {e}")