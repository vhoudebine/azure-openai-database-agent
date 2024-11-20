#!/bin/bash

# Download the Redshift ODBC driver for Linux (64-bit RPM)
apt-get install -y unixodbc-dev
curl https://s3.amazonaws.com/redshift-downloads/drivers/odbc/1.5.16.1019/AmazonRedshiftODBC-64-bit-1.5.16.1019-1.x86_64.deb -o AmazonRedshiftODBC-64-bit-1.5.16.1019-1.x86_64.deb

apt install ./AmazonRedshiftODBC-64-bit-1.5.16.1019-1.x86_64.deb
# Configure odbcinst.ini (replace placeholders with actual values)
echo "[Amazon Redshift (x64)]" >> /etc/odbcinst.ini
echo "Description = Amazon Redshift ODBC Driver" >> /etc/odbcinst.ini
echo "Driver = /opt/amazon/redshiftodbc/lib/64/libamazonredshiftodbc64.so" >> /etc/odbcinst.ini

# Update library paths (optional, adjust for your system)
echo 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/path/to/driver/lib' >> ~/.bashrc

# Reload configuration (optional)
source ~/.bashrc