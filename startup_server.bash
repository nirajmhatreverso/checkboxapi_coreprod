#!/bin/bash

/usr/bin/python3.9 /home/checkboxadmin/scripts/coreuat/manage.py runserver 0.0.0.0:8000 > /home/checkboxadmin/scripts/coreuat/logs/django_app.log 2>&1 & echo $! > /home/checkboxadmin/scripts/coreuat/api.pid

echo "################PROCESS ID #######################" 
cat /home/checkboxadmin/scripts/coreuat/api.pid
echo "#################################################"