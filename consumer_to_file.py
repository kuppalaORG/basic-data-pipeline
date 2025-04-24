from kafka import KafkaConsumer
import json
import clickhouse_connect

# client = clickhouse_connect.get_client(host='clickhouse', port=9000)
client = clickhouse_connect.get_client(host='localhost', port=8123)



consumer = KafkaConsumer(
    'dbserver1.testdb.employees',
    bootstrap_servers='kafka:9092',
    auto_offset_reset='earliest',
    group_id='clickhouse-consumer',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for msg in consumer:
    try:
        payload = msg.value.get('payload', {})
        op = payload.get('op')
        after = payload.get('after')
        before = payload.get('before')

        if op in ('c', 'r', 'u') and after:
            id = int(after.get('id'))
            name = after.get('name')
            salary = float(after.get('salary', 0))
            created_at = after.get('created_at', '2024-01-01 00:00:00')

            # UPSERT logic (ClickHouse doesn't support native UPDATE, emulate via REPLACE PARTITION if needed)
            client.command(f"ALTER TABLE testdb.employees DELETE WHERE id = {id}")
            client.insert('testdb.employees', [[id, name, salary, created_at]], column_names=['id', 'name', 'salary', 'created_at'])

            print(f"[UPSERT] {id}, {name}, {salary}, {created_at}")

        elif op == 'd' and before:
            id = int(before.get('id'))
            client.command(f"ALTER TABLE testdb.employees DELETE WHERE id = {id}")
            print(f"[DELETE] id: {id}")

    except Exception as e:
        print(f"Error processing message: {e}")
