#!/bin/bash

echo "Creating certs directory..."
# The -p flag means "create it if it doesn't exist, and don't error if it does"
mkdir -p certs

echo "Generating SSL Certificates for AAU..."
# We generate the certs
openssl req -x509 -newkey rsa:4096 -nodes -out certs/cert.pem -keyout certs/key.pem -days 365 -subj "/C=DK/ST=Nordjylland/L=Aalborg/O=AAU/CN=aau-rental"

echo "Certificates created successfully!"
