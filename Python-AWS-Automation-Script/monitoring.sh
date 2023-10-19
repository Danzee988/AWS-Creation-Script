#!/usr/bin/bash
#
# Some basic monitoring functionality; Tested on Amazon Linux 2.
#
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
MEMORYUSAGE=$(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2 }')
PROCESSES=$(expr $(ps -A | grep -c .) - 1)
HTTPD_PROCESSES=$(ps -A | grep -c httpd)
CPU_USAGE=$(top -b -n 1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
SYSTEM_UPDATES=$(yum list updates -q)

LOG_FILE="/var/log/monitoring.txt"

echo "Instance ID: $INSTANCE_ID" >> "$LOG_FILE"
echo "Memory utilisation: $MEMORYUSAGE" >> "$LOG_FILE"
echo "No of processes: $PROCESSES" >> "$LOG_FILE"
echo "CPU Usage: $CPU_USAGE%" >> "$LOG_FILE"
echo "System Updates:" >> "$LOG_FILE"
echo "$SYSTEM_UPDATES" >> "$LOG_FILE"
if [ $HTTPD_PROCESSES -ge 1 ]
then
    echo "Web server is running" >> "$LOG_FILE"
else
    echo "Web server is NOT running" >> "$LOG_FILE"
fi
