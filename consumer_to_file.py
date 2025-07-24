from kafka import KafkaConsumer
import json
import clickhouse_connect
import time

# Connect to ClickHouse (hosted on same EC2)
client = clickhouse_connect.get_client(host='localhost', port=8123)

# Connect to Kafka (running in Docker, but exposed to EC2 host on 9092)
consumer = KafkaConsumer(
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    group_id='clickhouse-consumer',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
    enable_auto_commit=True
)
# Keep track of subscribed topics to avoid re-subscription
consumer.subscribe(pattern=r'^dbserver1\.testdb\..*$')
subscribed_topics = set()

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

    ddl = f"""
    CREATE TABLE IF NOT EXISTS raw.{table_name} (
        {', '.join(cols)}
    ) ENGINE = MergeTree()
    ORDER BY id
    """
    client.command(ddl)

while True:
    all_topics = consumer.topics()
    new_topics = [t for t in all_topics if t.startswith("dbserver1.testdb.") and t not in subscribed_topics]

    for topic in new_topics:
        print(f"🟢 Subscribing to topic: {topic}")
        consumer.subscribe([topic])
        subscribed_topics.add(topic)

    for message in consumer:
        topic = message.topic
        table = topic.split('.')[-1]

        payload = message.value.get("payload")
        if payload is None:
            continue

        op = payload.get("op")
        if op in ["c", "u"]:  # create or update
            after = payload.get("after", {})
            if after:
                ensure_table(table, after)
                values = [[after[k] for k in after]]
                client.insert(f"raw.{table}", values, column_names=list(after.keys()))
                print(f"✅ Inserted into raw.{table}: {after}")

        elif op == "d":  # delete
            before = payload.get("before", {})
            if before:
                record_id = before.get("id")
                if record_id is not None:
                    client.command(f"ALTER TABLE raw.{table} DELETE WHERE id = {int(record_id)}")
                    print(f"🗑️ Deleted from raw.{table}: {record_id}")

    time.sleep(5)
