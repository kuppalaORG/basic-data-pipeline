from kafka import KafkaConsumer
import json
import clickhouse_connect
import time
import re
# Connect to ClickHouse (hosted on same EC2)
import re
import json
import time
import clickhouse_connect
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    group_id='clickhouse-consumer-test-01',  # Use new group ID for testing
    value_deserializer=lambda m: json.loads(m.decode('utf-8')) if m else None,
    enable_auto_commit=True
)

consumer.subscribe(pattern=re.compile(r'^dbserver1\.testdb\..*'))  # Only once!

while True:
    for message in consumer:
        topic = message.topic
        table = topic.split('.')[-1]

        payload = message.value.get("payload")
        if payload is None:
            continue

        op = payload.get("op")
        if op in ["c", "u", "r"]:  # ✅ include "r"
            after = payload.get("after", {})
            if after:
                ensure_table(table, after)
                values = [[after[k] for k in after]]
                client.insert(f"raw.{table}", values, column_names=list(after.keys()))
                print(f"✅ Inserted into raw.{table}: {after}")

        elif op == "d":
            before = payload.get("before", {})
            if before:
                record_id = before.get("id")
                if record_id is not None:
                    client.command(f"ALTER TABLE raw.{table} DELETE WHERE id = {int(record_id)}")
                    print(f"🗑️ Deleted from raw.{table}: {record_id}")
