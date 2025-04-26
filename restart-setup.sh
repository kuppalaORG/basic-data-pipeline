#!/bin/bash

set -e

echo "\ud83d\ude80 Cleaning up old containers..."
docker rm -f docker-zookeeper-1 docker-kafka-1 docker-connect-1 docker-mysql-1 clickhouse tabix-ui 2>/dev/null || true
sleep 3

echo "\u2705 Old containers removed."

# ---------------------
# Start Zookeeper
# ---------------------
echo "\ud83d\udd35 Starting Zookeeper..."
docker run -d --name docker-zookeeper-1 \
  --network basic-data-pipeline_kafka_net \
  -e ZOOKEEPER_CLIENT_PORT=2181 \
  confluentinc/cp-zookeeper:7.5.0
sleep 10
echo "\ud83d\udfe2 Zookeeper started."

# ---------------------
# Start Kafka
# ---------------------
echo "\ud83d\udd35 Starting Kafka..."
docker run -d --name docker-kafka-1 \
  --network basic-data-pipeline_kafka_net \
  -p 9092:9092 -p 29092:29092 \
  -e KAFKA_BROKER_ID=1 \
  -e KAFKA_ZOOKEEPER_CONNECT=docker-zookeeper-1:2181 \
  -e KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092,DOCKER://0.0.0.0:29092 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://172.31.14.166:9092,DOCKER://docker-kafka-1:29092 \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  confluentinc/cp-kafka:7.5.0
sleep 15
echo "\ud83d\udfe2 Kafka started."

# ---------------------
# Start MySQL
# ---------------------
echo "\ud83d\udd35 Starting MySQL..."
docker run -d --name docker-mysql-1 \
  --network basic-data-pipeline_kafka_net \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=testdb \
  -e MYSQL_USER=debezium \
  -e MYSQL_PASSWORD=dbz \
  -p 3306:3306 \
  mysql:8.0.36 \
  --server-id=223344 \
  --log-bin=mysql-bin \
  --binlog-format=ROW \
  --binlog-row-image=FULL \
  --gtid-mode=ON \
  --enforce-gtid-consistency=ON \
  --default-authentication-plugin=mysql_native_password
sleep 10
echo "\ud83d\udfe2 MySQL started."

# ---------------------
# Start ClickHouse
# ---------------------
echo "\ud83d\udd35 Starting ClickHouse..."
docker run -d --name clickhouse \
  --network basic-data-pipeline_kafka_net \
  -p 8123:8123 -p 9000:9000 \
  clickhouse/clickhouse-server:23.3
sleep 5
echo "\ud83d\udfe2 ClickHouse started."

# ---------------------
# Start Debezium Connect
# ---------------------
echo "\ud83d\udd35 Starting Debezium Connect..."
docker run -d --name docker-connect-1 \
  --network basic-data-pipeline_kafka_net \
  -p 8083:8083 \
  -e BOOTSTRAP_SERVERS=docker-kafka-1:29092 \
  -e GROUP_ID=1 \
  -e CONFIG_STORAGE_TOPIC=connect-configs \
  -e OFFSET_STORAGE_TOPIC=connect-offsets \
  -e STATUS_STORAGE_TOPIC=connect-statuses \
  -e KEY_CONVERTER_SCHEMAS_ENABLE=false \
  -e VALUE_CONVERTER_SCHEMAS_ENABLE=false \
  -e CONNECT_KEY_CONVERTER=org.apache.kafka.connect.json.JsonConverter \
  -e CONNECT_VALUE_CONVERTER=org.apache.kafka.connect.json.JsonConverter \
  -e CONNECT_INTERNAL_KEY_CONVERTER=org.apache.kafka.connect.json.JsonConverter \
  -e CONNECT_INTERNAL_VALUE_CONVERTER=org.apache.kafka.connect.json.JsonConverter \
  -e CONNECT_PLUGIN_PATH=/kafka/connect,/usr/share/java,/debezium-plugins \
  quay.io/debezium/connect:2.6
sleep 20
echo "\ud83d\udfe2 Debezium Connect started."

# ---------------------
# Post MySQL user adjustments (optional)
# ---------------------
echo "\ud83d\udd35 Setting MySQL user privileges..."
docker exec -i docker-mysql-1 mysql -u root -proot -e "\
     ALTER USER 'root'@'%' IDENTIFIED BY 'root';\n\
     ALTER USER 'root'@'localhost' IDENTIFIED BY 'root';\n\
     FLUSH PRIVILEGES;"
sleep 2
echo "\ud83d\udfe2 MySQL root password reset completed."

# ---------------------
# Final Status
# ---------------------
echo "\u2705 All containers started successfully!"
docker ps
