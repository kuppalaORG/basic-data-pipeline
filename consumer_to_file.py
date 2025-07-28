from kafka import KafkaConsumer,TopicPartition
import json
import clickhouse_connect
import time


topic = 'dbserver1.testdb.employees'

consumer = KafkaConsumer(
    bootstrap_servers=['localhost:9092'],
    auto_offset_reset='earliest',
    enable_auto_commit=False,
    consumer_timeout_ms=10000
)

partition = TopicPartition(topic, 0)
consumer.assign([partition])  # ✅ Manual assignment — works reliably

print("Assigned partitions:", consumer.assignment())

for message in consumer:
    print("✅ Message received:")
    print("Key:", message.key)
    print("Value:", message.value.decode('utf-8'))
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

for message in consumer:
    try:
        print("📨 Message received.")
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
                    print(f" Deleted from raw.{table}: {record_id}")

    except Exception as e:
        print(f"Error processing message: {e}")
