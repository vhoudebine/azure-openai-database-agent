#!/bin/bash

# Download the Redshift ODBC driver for Linux (64-bit RPM)
wget https://s3.amazonaws.com/redshift-downloads/drivers/odbc/1.5.16.1019/AmazonRedshiftODBC-64-bit-1.5.16.1019-1.x86_64.deb

# Install the driver using yum
sudo apt install ./AmazonRedshiftODBC-64-bit-1.5.16.1019-1.x86_64.deb

