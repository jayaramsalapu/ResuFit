#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install Tesseract OCR system package if running in Linux environment with apt-get
if command -v apt-get &> /dev/null; then
  echo "Installing Tesseract OCR system dependencies..."
  apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-eng libtesseract-dev
fi

# Upgrade pip and install Python requirements
python -m pip install --upgrade pip
pip install -r requirements.txt
