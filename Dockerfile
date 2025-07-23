# Dockerfile for enhanced Debezium Connect with extra tools
FROM quay.io/debezium/connect:2.6

USER root
RUN microdnf install -y iputils mysql && microdnf clean all
USER kafka
