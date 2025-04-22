from kafka import KafkaConsumer
import json
import clickhouse_connect

# Connect to ClickHouse
client = clickhouse_connect.get_client(host='localhost', port=9000)

# Kafka consumer
consumer = KafkaConsumer(
    'dbserver1.testdb.employees',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    group_id='clickhouse-consumer',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for msg in consumer:
    try:
        value = msg.value
        # Extract record from Debezium envelope
        payload = value.get('payload', {})
        after = payload.get('after', {})
        if after:
            id = int(after.get('id', 0))
            name = after.get('name', '')
            salary = float(after.get('salary', 0))
            created_at = after.get('created_at', '2024-01-01 00:00:00')

            # Insert into ClickHouse
            client.insert(
                'testdb.employees',
                [[id, name, salary, created_at]],
                column_names=['id', 'name', 'salary', 'created_at']
            )

            print(f"Inserted record: {id}, {name}, {salary}, {created_at}")

    except Exception as e:
        print(f"Error processing message: {e}")
