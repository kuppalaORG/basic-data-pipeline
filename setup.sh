#!/bin/bash

set -e

################################################################################
# 🚀 Debezium CDC Pipeline Setup for Amazon Linux 2 (AMI Linux 2)
# 🛠️ Prerequisites: 
#   - Run: chmod +x setup.sh
#   - Execute: ./setup.sh
# 📌 Note: Tested on EC2 instance with AMI Linux 2 (Amazon Linux 2 AMI 2.0)
################################################################################

echo "🔧 Installing Docker..."
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

echo "🐳 Installing Docker Compose..."
DOCKER_COMPOSE_VERSION=1.29.2
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "📁 Setting up CDC pipeline directory..."
mkdir -p ~/basic-data-pipeline
cd ~/basic-data-pipeline

echo "📦 Writing docker-compose.yml..."
cat > docker-compose.yml <<'EOF'
version: '3'
services:

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    hostname: kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  mysql:
    image: mysql:8.0.36
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_USER: debezium
      MYSQL_PASSWORD: dbz
      MYSQL_DATABASE: testdb
    command:
      --server-id=223344
      --log-bin=mysql-bin
      --binlog-format=ROW
      --binlog-row-image=FULL
      --gtid-mode=ON
      --enforce-gtid-consistency=ON
      --default-authentication-plugin=mysql_native_password
    volumes:
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql

  connect:
    image: quay.io/debezium/connect:2.6
    ports:
      - "8083:8083"
    depends_on:
      - kafka
      - mysql
    environment:
      BOOTSTRAP_SERVERS: kafka:9092
      GROUP_ID: 1
      CONFIG_STORAGE_TOPIC: connect-configs
      OFFSET_STORAGE_TOPIC: connect-offsets
      STATUS_STORAGE_TOPIC: connect-status
      KEY_CONVERTER_SCHEMAS_ENABLE: "false"
      VALUE_CONVERTER_SCHEMAS_ENABLE: "false"
      CONNECT_PLUGIN_PATH: /kafka/connect,/usr/share/java,/debezium-plugins
      SCHEMA_HISTORY_INTERNAL_KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    volumes:
      - ./plugins:/debezium-plugins
EOF

echo "📄 Writing init.sql..."
cat > init.sql <<'EOF'
CREATE DATABASE IF NOT EXISTS testdb;

USE testdb;

CREATE TABLE IF NOT EXISTS employees (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255),
    role VARCHAR(255)
);

INSERT INTO employees (name, role)
VALUES ('Bharath', 'Engineer'), ('Arjun', 'Analyst');

GRANT SELECT, RELOAD, SHOW DATABASES, REPLICATION SLAVE, REPLICATION CLIENT, LOCK TABLES ON *.* TO 'debezium'@'%';
FLUSH PRIVILEGES;
EOF

echo "🚀 Bringing up Docker containers..."
docker-compose up -d

echo "⏳ Waiting for Kafka Connect to be ready..."
sleep 30

echo "🔌 Creating connector registration script..."
cat > register-connector.sh <<'EOF'
#!/bin/bash

echo "🔌 Registering Debezium MySQL Connector..."

curl -s -o response.json -w "%{http_code}" -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mysql-connector",
    "config": {
      "connector.class": "io.debezium.connector.mysql.MySqlConnector",
      "database.hostname": "mysql",
      "database.port": "3306",
      "database.user": "debezium",
      "database.password": "dbz",
      "database.server.id": "184054",
      "topic.prefix": "dbserver1",
      "database.include.list": "testdb",
      "table.include.list": "testdb.employees",
      "include.schema.changes": "false",
      "schema.history.internal.kafka.bootstrap.servers": "kafka:9092",
      "schema.history.internal.kafka.topic": "schema-changes.testdb"
    }
  }' > status.txt

STATUS=$(cat status.txt)

if [[ "$STATUS" == "201" ]]; then
  echo "✅ Connector created successfully!"
elif [[ "$STATUS" == "409" ]]; then
  echo "⚠️ Connector already exists!"
else
  echo "❌ Connector creation failed. Status Code: $STATUS"
  cat response.json
fi

rm -f status.txt response.json
EOF

chmod +x register-connector.sh
./register-connector.sh

echo "🎉 ✅ Debezium CDC pipeline fully deployed and connector registered!"
