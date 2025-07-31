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
DLQ_PATH = 'dlq_errors.txt'
# Setup DLQ file
if not os.path.exists(DLQ_PATH):
    open(DLQ_PATH, 'w').close()
#Initialize ClickHouse client
client = clickhouse_connect.get_client(host='localhost', port=8123, username='default', password='')

def write_to_dlq(message, error, table=None, column=None, value=None):
    with open(DLQ_PATH, 'a') as f:
        f.write("🔥 INSERT FAILURE\n")
        if table:
            f.write(f"Table: {table}\n")
        if column:
            f.write(f"Column: {column}\n")
        if value is not None:
            f.write(f"Offending Value: {repr(value)}\n")
        f.write(f"Error: {error}\n")
        if "table" in error.lower():
            f.write("💥 Hint: Table might have been dropped or not yet created!\n")
        f.write("Payload:\n")
        f.write(json.dumps(message, indent=2, default=str))
        f.write("\n" + "-"*80 + "\n")

def normalize_value(value):
    try:
        if value is None:
            return ''
        elif isinstance(value, (int, float)) and value > 1e12:
            return int(value) // 1000
        elif isinstance(value, bool):
            return int(value)
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        elif isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, (dict, list)):
                    return value
            except:
                pass
            return value
        elif isinstance(value, (dict, list, tuple)):
            return json.dumps(value, default=str)
        else:
            return str(value)
    except Exception as e:
        return f"[ERROR: {e}]"

def infer_clickhouse_type(value):
    if isinstance(value, bool):
        return "UInt8"
    elif isinstance(value, int):
        return "Int64"
    elif isinstance(value, float):
        return "Float64"
    elif isinstance(value, str):
        return "String"
    elif isinstance(value, dict) or isinstance(value, list):
        return "String"
    else:
        return "String"

def ensure_table(table_name, sample_record):
    if table_name in created_tables:
        return

    cols = []
    for k, v in sample_record.items():
        if k in ["value", "source_params", "child_config", "config"]:
            col_type = "String"
        elif k.endswith("_on") and isinstance(v, (int, float)) and v > 1e12:
            col_type = "DateTime"
        else:
            col_type = infer_clickhouse_type(v)
        cols.append(f"{k} {col_type}")

    order_by = next((key for key in PRIMARY_KEY_CANDIDATES if key in sample_record), list(sample_record.keys())[0])

    ddl = f"""
    CREATE TABLE IF NOT EXISTS raw.{table_name} (
        {', '.join(cols)}
    ) ENGINE = MergeTree()
    ORDER BY {order_by}
    """
    client.command(ddl)
    created_tables.add(table_name)
    print(f"🛠 Ensured table raw.{table_name} with ORDER BY {order_by}")

def alter_table_if_new_keys(table_name, record):
    desc_output = client.command(f"DESCRIBE TABLE raw.{table_name}")
    existing_cols = {line.split()[0] for line in desc_output.strip().splitlines()}

    new_cols = []
    for key, value in record.items():
        if key not in existing_cols:
            col_type = infer_clickhouse_type(value)
            new_cols.append((key, col_type))

    for key, col_type in new_cols:
        alter_cmd = f"ALTER TABLE raw.{table_name} ADD COLUMN IF NOT EXISTS {key} {col_type}"
        client.command(alter_cmd)
        print(f"➕ Added column: {key} ({col_type}) to raw.{table_name}")


# Discover topics
admin = AdminClient({'bootstrap.servers': BOOTSTRAP_SERVERS})
metadata = admin.list_topics(timeout=10)
topics = [t for t in metadata.topics if any(t.startswith(p) for p in VALID_PREFIXES)]

if not topics:
    print("❌ No matching topics found with prefix:", VALID_PREFIXES)
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
# Consumer logic
print("📡 Topics detected:", topics)
print(" Subscribed to topics")
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
                    try:
                        # Normalize and create table
                        normalized_record = {k: normalize_value(v) for k, v in after.items()}
                        ensure_table(table, normalized_record)
                        alter_table_if_new_keys(table, normalized_record)

                        # Insert
                        client.insert_dicts(f"raw.{table}", [normalized_record])
                    except Exception as insert_err:
                        # Pinpoint problematic key if possible
                        for key, value in normalized_record.items():
                            try:
                                client.insert_dicts(f"raw.{table}", [{key: value}])
                            except Exception as col_err:
                                write_to_dlq(after, str(col_err), table, key, value)
                                break  # break after first offending column
                        else:
                            # fallback if not caught by column-level test
                            write_to_dlq(after, str(insert_err), table)

            elif op == "d":
                before = payload.get("before", {})
                record_id = before.get("uuid") or before.get("id")
                if record_id:
                    where_clause = f"id = '{record_id}'" if isinstance(record_id, str) else f"id = {record_id}"
                    try:
                        client.command(f"ALTER TABLE raw.{table} DELETE WHERE {where_clause}")
                        print(f"🗑 Deleted from raw.{table}: {record_id}")
                    except Exception as delete_err:
                        write_to_dlq(before, str(delete_err), table)

        except Exception as e:
            print("⚠ Top-level error:", e)
            write_to_dlq(msg.value().decode('utf-8'), str(e))

except KeyboardInterrupt:
    print("Interrupted by user")

finally:
    consumer.close()
    print("🔒 Consumer closed")