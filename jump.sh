#!/bin/bash

# Usage: ./jump.sh kafka
#        ./jump.sh mysql
#        ./jump.sh connect
#        ./jump.sh zookeeper
#        ./jump.sh clickhouse
#chmod +x jump.sh

case $1 in
  kafka)
    docker exec -it docker-kafka-1 bash
    ;;
  mysql)
    docker exec -it docker-mysql-1 bash
    ;;
  connect)
    docker exec -it docker-connect-1 bash
    ;;
  zookeeper)
    docker exec -it docker-zookeeper-1 bash
    ;;
  clickhouse)
    docker exec -it clickhouse bash
    ;;
  *)
    echo "Usage: $0 {kafka|mysql|connect|zookeeper|clickhouse}"
    ;;
esac
