from kafka import KafkaConsumer, TopicPartition
import json
import clickhouse_connect
import time

client = clickhouse_connect.get_client(host='localhost', port=8123)
consumer = KafkaConsumer(
    bootstrap_servers='172.31.14.166:9092',
    auto_offset_reset='earliest',
    group_id='clickhouse-consumer',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None
)

def ensure_table(table_name, sample_record):
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

    ddl = f"CREATE TABLE IF NOT EXISTS raw.{table_name} ({', '.join(cols)}) ENGINE = MergeTree() ORDER BY id"
    client.command(ddl)

while True:
    topics = consumer.topics()
    for topic in topics:
        if topic.startswith("dbserver1.testdb."):
            consumer.subscribe([topic])
            print(f"🟢 Subscribed to topic: {topic}")

            for msg in consumer:
                payload = msg.value.get('payload')
                table = topic.split('.')[-1]

                if payload is None:
                    continue

                op = payload.get('op')
                if op in ['c', 'u']:
                    after = payload.get('after', {})
                    if after:
                        ensure_table(table, after)
                        values = [[after[k] for k in after]]
                        client.insert(f'raw.{table}', values, column_names=list(after.keys()))
                        print(f"✅ Inserted into raw.{table}: {after}")
                elif op == 'd':
                    before = payload.get('before', {})
                    if before:
                        id = int(before.get('id'))
                        client.command(f"ALTER TABLE raw.{table} DELETE WHERE id = {id}")
                        print(f"🗑️ Deleted from raw.{table}: {id}")
    time.sleep(10)
