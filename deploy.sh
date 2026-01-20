#!/bin/bash
cd /root/poly-scout
pkill -f 'python.*daemon' 2>/dev/null
sleep 1
nohup python3 -m src.daemon > /tmp/scout.log 2>&1 &
sleep 5
head -60 /tmp/scout.log
