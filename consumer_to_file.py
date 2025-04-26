from kafka import KafkaConsumer
import json
import clickhouse_connect

# Connect to ClickHouse (HTTP port 8123)
client = clickhouse_connect.get_client(host='localhost', port=8123)

# Kafka consumer
consumer = KafkaConsumer(
    'dbserver1.testdb.employees',
    bootstrap_servers='172.31.14.166:9092',
    auto_offset_reset='earliest',
    group_id='clickhouse-consumer',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None
)

print("Connected topics:", consumer.topics())

for msg in consumer:
    if msg.value is None:
        print("⚠️  Skipped null message.")
        continue

    try:
        value = msg.value
        payload = value.get('payload', {})
        op = payload.get('op')  # c (create), u (update), d (delete)

        if op in ['c', 'u']:
            after = payload.get('after', {})
            if after:
                id = int(after.get('id'))
                name = after.get('name', '')
                salary = float(after.get('salary', 0))
                created_at = after.get('created_at', '2024-01-01 00:00:00')

                # Upsert = delete old + insert new
                client.command(f"ALTER TABLE testdb.employees DELETE WHERE id = {id}")
                client.insert(
                    'testdb.employees',
                    [[id, name, salary, created_at]],
                    column_names=['id', 'name', 'salary', 'created_at']
                )
                print(f"✅ Upserted record: {id}, {name}, {salary}, {created_at}")

        elif op == 'd':
            before = payload.get('before', {})
            if before:
                id = int(before.get('id'))
                client.command(f"ALTER TABLE testdb.employees DELETE WHERE id = {id}")
                print(f"🗑️ Deleted record: {id}")

    except Exception as e:
        print(f"❌ Error processing message: {e}")
