#!/bin/bash

set -e

echo "🚀 Cleaning up old containers..."

docker rm -f docker-zookeeper-1 docker-kafka-1 docker-connect-1 docker-mysql-1 clickhouse tabix-ui 2>/dev/null || true

sleep 3

echo "✅ Old containers removed."

echo "🔵 Starting Zookeeper..."
docker run -d --name docker-zookeeper-1 \
  --network basic-data-pipeline_kafka_net \
  -e ZOOKEEPER_CLIENT_PORT=2181 \
  confluentinc/cp-zookeeper:7.5.0

sleep 10

echo "🟢 Zookeeper started."

echo "🔵 Starting Kafka..."
docker run -d --name docker-kafka-1 \
  --network basic-data-pipeline_kafka_net \
  -p 9092:9092 -p 29092:29092 \
  -e KAFKA_BROKER_ID=1 \
  -e KAFKA_ZOOKEEPER_CONNECT=docker-zookeeper-1:2181 \
  -e KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092,DOCKER://0.0.0.0:29092 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://172.31.14.166:9092,DOCKER://docker-kafka-1:29092 \
  -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,DOCKER:PLAINTEXT \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  confluentinc/cp-kafka:7.5.0

sleep 15

echo "🟢 Kafka started."

echo "🔵 Starting MySQL..."
docker run -d --name docker-mysql-1 \
  --network basic-data-pipeline_kafka_net \
  -e MYSQL_ROOT_PASSWORD=debezium \
  -e MYSQL_DATABASE=testdb \
  -e MYSQL_USER=debezium \
  -e MYSQL_PASSWORD=dbz \
  -p 3306:3306 \
  mysql:8.0.36

sleep 15
echo "🟢 MySQL started."

echo "🔵 Waiting for MySQL to be ready..."

# Retry until MySQL is ready
until docker exec docker-mysql-1 mysqladmin ping -uroot -pdebezium --silent &>/dev/null; do
  printf "."
  sleep 2
done

echo "🟢 MySQL is ready."

echo "⚙️ Setting up MySQL permissions..."
docker exec -i docker-mysql-1 mysql -uroot -pdebezium <<EOF
ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'debezium';
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'debezium';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost';
GRANT ALL PRIVILEGES ON *.* TO 'debezium'@'%';
FLUSH PRIVILEGES;
EOF

echo "✅ MySQL permissions set."



echo "🔵 Starting ClickHouse..."
docker run -d --name clickhouse \
  --network basic-data-pipeline_kafka_net \
  -p 8123:8123 -p 9000:9000 \
  clickhouse/clickhouse-server:23.3

sleep 10

echo "🟢 ClickHouse started."

echo "🔵 Starting Debezium Connect..."
docker run -d --name docker-connect-1 \
  --network basic-data-pipeline_kafka_net \
  -p 8083:8083 \
  -e BOOTSTRAP_SERVERS=docker-kafka-1:29092 \
  -e GROUP_ID=1 \
  -e CONFIG_STORAGE_TOPIC=connect-configs \
  -e OFFSET_STORAGE_TOPIC=connect-offsets \
  -e STATUS_STORAGE_TOPIC=connect-statuses \
  -e CONNECT_KEY_CONVERTER=org.apache.kafka.connect.json.JsonConverter \
  -e CONNECT_VALUE_CONVERTER=org.apache.kafka.connect.json.JsonConverter \
  -e CONNECT_INTERNAL_KEY_CONVERTER=org.apache.kafka.connect.json.JsonConverter \
  -e CONNECT_INTERNAL_VALUE_CONVERTER=org.apache.kafka.connect.json.JsonConverter \
  -e CONNECT_REST_ADVERTISED_HOST_NAME=connect \
  quay.io/debezium/connect:2.6

sleep 20

echo "🔄 Changing MySQL root password for compatibility..."
docker exec -i docker-mysql-1 mysql -uroot -proot -e "
    ALTER USER 'root'@'%' IDENTIFIED BY 'debezium';
    ALTER USER 'root'@'localhost' IDENTIFIED BY 'debezium';
    FLUSH PRIVILEGES;
"

echo "🟢 Debezium Connect started."

echo "🟢 Creation of db in Clickhouse."


docker exec -it clickhouse clickhouse-client --query "
CREATE DATABASE IF NOT EXISTS testdb;
CREATE TABLE IF NOT EXISTS testdb.employees (
    id Int32,
    name String,
    position String,
    salary Float64,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree() ORDER BY id;
"

echo  "Created Db in Clickhouse"
echo "✅ All containers started successfully!"
docker ps
