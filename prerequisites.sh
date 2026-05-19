#!/bin/bash
# prerequisites.sh
# Installs all necessary tools & libraries for Ubuntu 24.04

set -e

echo "Updating system and installing base dependencies..."
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y python3 python3-venv python3-pip curl git nginx

echo "Installing Node.js and NPM..."
# Using NodeSource for the latest Node.js LTS (v20.x)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo "Verifying installations..."
python3 --version
node --version
npm --version

echo "=========================================="
echo "Prerequisites installed successfully!"
echo "=========================================="
