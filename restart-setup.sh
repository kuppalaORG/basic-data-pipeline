#!/bin/bash

echo "🚀 Cleaning up old containers..."

docker rm -f docker-zookeeper-1 docker-kafka-1 docker-connect-1 docker-mysql-1 clickhouse tabix-ui 2>/dev/null

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
  -p 9092:9092 \
  -e KAFKA_BROKER_ID=1 \
  -e KAFKA_ZOOKEEPER_CONNECT=docker-zookeeper-1:2181 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://172.31.14.166:9092 \
  -e KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092 \
  confluentinc/cp-kafka:7.5.0

sleep 10

echo "🟢 Kafka started."

# OPTIONAL: Start MySQL
echo "🔵 Starting MySQL..."
docker run -d --name docker-mysql-1 \
  --network basic-data-pipeline_kafka_net \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=testdb \
  -e MYSQL_USER=debezium \
  -e MYSQL_PASSWORD=dbz \
  -p 3306:3306 \
  mysql:8.0.36

sleep 10

echo "🟢 MySQL started."

# OPTIONAL: Start ClickHouse
echo "🔵 Starting ClickHouse..."
docker run -d --name clickhouse \
  --network basic-data-pipeline_kafka_net \
  -p 8123:8123 -p 9000:9000 \
  clickhouse/clickhouse-server:23.3

sleep 10

echo "🟢 ClickHouse started."

# OPTIONAL: Start Debezium Connect
echo "🔵 Starting Debezium Connect..."
docker run -d --name docker-connect-1 \
  --network basic-data-pipeline_kafka_net \
  -p 8083:8083 \
  -e BOOTSTRAP_SERVERS=docker-kafka-1:9092 \
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

sleep 10
docker exec -i docker-mysql-1 mysql -u root -e "
    ALTER USER 'root'@'%' IDENTIFIED BY 'debezium';
    ALTER USER 'root'@'localhost' IDENTIFIED BY 'debezium';
    FLUSH PRIVILEGES;
"
echo "🟢 Debezium Connect started."

echo "✅ All containers started successfully!"
docker ps
