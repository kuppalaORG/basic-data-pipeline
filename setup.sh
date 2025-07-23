#!/bin/bash

set -e

################################################################################
# 🚀 Debezium CDC Pipeline Setup for Amazon Linux 2 (AMI Linux 2)
# 🛠️ Prerequisites:
#   - Run: chmod +x setup.sh
#   - Execute: ./setup.sh
################################################################################
echo "🔧 Installing Docker..."
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker

echo "👤 Adding current user to docker group..."
sudo usermod -aG docker ec2-user

# Ensure correct permissions on Docker socket immediately
echo "🔒 Setting Docker socket permissions..."
sudo chmod 666 /var/run/docker.sock


echo "🐳 Installing Docker Compose..."
DOCKER_COMPOSE_VERSION=1.29.2
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "📁 Navigating to CDC directory..."
mkdir -p ~/basic-data-pipeline
cd ~/basic-data-pipeline

echo "📄 Creating init.sql..."
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

echo "🧪 Creating init.sh for ClickHouse..."
cat > init.sh <<'EOF'
#!/bin/bash
clickhouse-client --query="CREATE DATABASE IF NOT EXISTS raw;"
EOF
chmod +x init.sh

echo "🚀 Starting Docker Compose services..."
docker-compose up -d

echo "⏳ Waiting for Kafka Connect to be ready..."
until curl -s http://localhost:8083/ | grep -q "Kafka Connect"; do
  echo "⌛ Kafka Connect not ready yet. Retrying in 5 seconds..."
  sleep 5
done
echo "✅ Kafka Connect is ready!"

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

echo "✅ Done. All services are up!"
