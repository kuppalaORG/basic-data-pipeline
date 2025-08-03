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
sudo dnf install -y libxcrypt-compat

echo "👤 Adding current user to docker group..."
sudo usermod -aG docker ec2-user

echo "🔧 Preparing EBS volumes..."
# Optional check if mounted
if ! mount | grep -q "/mnt/data"; then
  echo "❌ /mnt/data not mounted. Please mount EBS volume before proceeding."
  exit 1
fi

# ClickHouse volume
sudo mkdir -p /mnt/data/clickhouse
sudo chown -R 101:101 /mnt/data/clickhouse

# MySQL volume
sudo mkdir -p /mnt/data/mysql
sudo chown -R 999:999 /mnt/data/mysql

# Optional: Jupyter notebooks dir
mkdir -p /home/ec2-user/notebooks

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

echo "🐍 Installing Python and dependencies..."
sudo dnf install -y python3 python3-pip

if [ -f requirements.txt ]; then
  pip3 install --no-cache-dir -r requirements.txt
else
  echo "⚠️ No requirements.txt found, skipping pip install."
fi

echo "⏳ Delaying Jupyter launch by 3 minutes..."
(sleep 180 && nohup jupyter notebook --notebook-dir=/home/ec2-user/notebooks \
  --ip=0.0.0.0 --port=8888 --no-browser > jupyter.log 2>&1 &) &
echo "📓 Jupyter Notebook will be available at: http://<EC2-PUBLIC-IP>:8888"
echo "🔑 Check jupyter.log for token or configure token manually."

echo "⌛ Waiting for Kafka Connect to be ready..."
while true; do
  STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8083)
  echo "🔍 HTTP Status: $STATUS_CODE"

  if [ "$STATUS_CODE" -eq 200 ]; then
    echo "✅ Kafka Connect is ready!"
    break
  fi

  echo "⌛ Kafka Connect not ready yet. Retrying in 5 seconds..."
  sleep 5
done

echo "🔌 Registering Kafka connector if script exists..."
if [ -f register-connector.sh ]; then
  chmod +x register-connector.sh
#  ./register-connector.sh
else
  echo "⚠️ register-connector.sh not found. Skipping connector registration."
fi

echo "🚀 Starting Kafka-to-ClickHouse consumer in background..."
#nohup python3 consumer_to_file.py > consumer.log 2>&1 &

echo "✅ Setup complete. All services are up and running."