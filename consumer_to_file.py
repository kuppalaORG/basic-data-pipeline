from confluent_kafka import Consumer, KafkaException
from confluent_kafka.admin import AdminClient
import clickhouse_connect
import json
import time
import os

# Kafka and ClickHouse settings
BOOTSTRAP_SERVERS = 'localhost:29092'
VALID_PREFIXES = ['config.', 'sourcing.']
DLQ_PATH = 'dlq_errors.txt'
POLL_TIMEOUT = 5.0

# Mapping MySQL types to ClickHouse types (for simulation via Python types)
TYPE_MAPPING = {
    'tinyint': 'Int8',
    'smallint': 'Int16',
    'mediumint': 'Int32',
    'int': 'Int32',
    'integer': 'Int32',
    'bigint': 'Int64',
    'float': 'Float32',
    'double': 'Float64',
    'decimal': 'Float64',

    'bit': 'UInt8',
    'boolean': 'UInt8',
    'bool': 'UInt8',

    'char': 'String',
    'varchar': 'String',
    'text': 'String',
    'tinytext': 'String',
    'mediumtext': 'String',
    'longtext': 'String',

    'blob': 'String',
    'tinyblob': 'String',
    'mediumblob': 'String',
    'longblob': 'String',

    'date': 'Date',
    'datetime': 'DateTime',
    'timestamp': 'DateTime',
    'time': 'String',
    'year': 'UInt16',

    'json': 'String',
    'uuid': 'UUID',
    'binary': 'String',
    'varbinary': 'String',
    'enum': 'String',

    'null': 'String',  # fallback
}

PRIMARY_KEY_CANDIDATES = ['uuid', 'id', 'pk', 'employee_id', 'record_id']
created_tables = set()

# Setup DLQ file
if not os.path.exists(DLQ_PATH):
    open(DLQ_PATH, 'w').close()

def write_to_dlq(message, error):
    with open(DLQ_PATH, 'a') as f:
        f.write(f"ERROR: {error}\nMESSAGE: {json.dumps(message)}\n\n")

# Discover topics
admin = AdminClient({'bootstrap.servers': BOOTSTRAP_SERVERS})
metadata = admin.list_topics(timeout=10)
topics = [t for t in metadata.topics if any(t.startswith(p) for p in VALID_PREFIXES)]
if not topics:
    print(" No matching topics found with prefix:", VALID_PREFIXES)
    exit(1)
print("📡 Topics detected:", topics)

# Kafka consumer setup
consumer = Consumer({
    'bootstrap.servers': BOOTSTRAP_SERVERS,
    'group.id': 'clickhouse-dynamic-' + str(int(time.time())),
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': True,
})
consumer.subscribe(topics)
print(" Subscribed to topics")

# ClickHouse setup
client = clickhouse_connect.get_client(host='localhost', port=8123)
client.command("CREATE DATABASE IF NOT EXISTS raw")
def normalize_value(value):
    try:
        if value is None:
            return ''
        elif isinstance(value, (bool, int, float, str)):
            # Convert large timestamps (likely milliseconds) to seconds
            if isinstance(value, (int, float)) and value > 1e12:
                return int(value) // 1000
            return value
        elif isinstance(value, (dict, list, tuple)):
            return json.dumps(value, default=str)
        elif isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        else:
            return str(value)
    except Exception as e:
        return f"[ERROR: {e}]"

def infer_clickhouse_type(value):
    return TYPE_MAPPING.get(type(value), 'String')

def ensure_table(table_name, sample_record):
    if table_name in created_tables:
        return

    cols = []  # ✅ FIXED: declared outside loop

    for k, v in sample_record.items():
        if k in ["value", "source_params", "child_config", "config"]:
            col_type = "String"
        elif k.endswith("_on") and isinstance(v, (int, float)) and v > 1e12:
            col_type = "DateTime"
        else:
            col_type = infer_clickhouse_type(v)

        cols.append(f"{k} {col_type}")  # ✅ only append once

    order_by = next((key for key in PRIMARY_KEY_CANDIDATES if key in sample_record), list(sample_record.keys())[0])
    ddl = f"""
    CREATE TABLE IF NOT EXISTS raw.{table_name} (
        {', '.join(cols)}
    ) ENGINE = MergeTree()
    ORDER BY {order_by}
    """
    client.command(ddl)
    created_tables.add(table_name)
    print(f"🛠Ensured table raw.{table_name} with ORDER BY {order_by}")

# Start consuming
print(" Listening to Debezium topics...")
try:
    while True:
        msg = consumer.poll(POLL_TIMEOUT)
        if msg is None:
            print("⌛ Waiting for message...")
            continue
        if msg.error():
            print(" Kafka error:", msg.error())
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
                    try:
                        normalized_row = [normalize_value(v) for v in after.values()]
                        client.insert(f"raw.{table}", [normalized_row], column_names=list(after.keys()))
                    except Exception as insert_err:
                        print("⚠ Insert error:", insert_err)
                        write_to_dlq(after, str(insert_err))

            elif op == "d":
                before = payload.get("before", {})
                record_id = before.get("uuid") or before.get("id")
                if record_id:
                    where_clause = f"id = '{record_id}'" if isinstance(record_id, str) else f"id = {record_id}"
                    try:
                        client.command(f"ALTER TABLE raw.{table} DELETE WHERE {where_clause}")
                        print(f"Deleted from raw.{table}: {record_id}")
                    except Exception as delete_err:
                        print("⚠ Delete error:", delete_err)
                        write_to_dlq(before, str(delete_err))

        except Exception as e:
            print("⚠ Top-level message error:", e)
            write_to_dlq(msg.value().decode('utf-8'), str(e))

except KeyboardInterrupt:
    print("Interrupted by user")

finally:
    consumer.close()
    print("🔒 Consumer closed")