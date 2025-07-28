from confluent_kafka import Consumer
import clickhouse_connect
import json
import time

topic = 'dbserver1.testdb.employees'

consumer = Consumer({
    'bootstrap.servers': 'localhost:29092',
    'group.id': 'confluent-test-' + str(int(time.time())),
    'auto.offset.reset': 'earliest'
})

consumer.subscribe([topic])
print("🚀 Subscribed to topic:", topic)

client = clickhouse_connect.get_client(host='localhost', port=8123)
client.command("CREATE DATABASE IF NOT EXISTS raw")
created_tables = set()

def ensure_table(table_name, sample_record):
    if table_name in created_tables:
        return
    cols = []
    for k, v in sample_record.items():
        col_type = 'Int64' if k == 'id' else (
            'Float64' if isinstance(v, float) else
            'Int64' if isinstance(v, int) else
            'String'
        )
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

try:
    while True:
        msg = consumer.poll(timeout=5.0)
        if msg is None:
            print("⏳ Waiting for message...")
            continue
        if msg.error():
            print("Kafka error:", msg.error())
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
                    print(f" Inserted into raw.{table}: {after}")

            elif op == "d":
                before = payload.get("before", {})
                record_id = before.get("id")
                if record_id is not None:
                    client.command(f"ALTER TABLE raw.{table} DELETE WHERE id = {int(record_id)}")
                    print(f" Deleted from raw.{table}: {record_id}")

        except Exception as e:
            print(" Processing error:", e)

except KeyboardInterrupt:
    print(" Stopped by user")

finally:
    consumer.close()