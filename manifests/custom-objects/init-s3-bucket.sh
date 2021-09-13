#!/bin/bash

echo "Starting ensure-s3-bucket-exists"
cd ~
apt update && apt install curl unzip -y
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install
export AWS_ACCESS_KEY_ID=admin
export AWS_SECRET_ACCESS_KEY=password
export AWS_DEFAULT_REGION=us-west-2
aws --endpoint-url='http://moto:5000' s3api create-bucket --bucket output-bucket
aws --endpoint-url='http://moto:5000' s3api create-bucket --bucket artifacts
echo "Completed ensure-s3-bucket-exists"