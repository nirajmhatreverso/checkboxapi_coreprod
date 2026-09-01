#!/bin/bash

/usr/bin/python3.9 /home/checkboxadmin/scripts/coredev/manage.py runserver 0.0.0.0:7000 > /home/checkboxadmin/scripts/coredev/logs/django_app.log 2>&1 & echo $! > /home/checkboxadmin/scripts/coredev/api.pid

echo "################PROCESS ID #######################"
cat /home/checkboxadmin/scripts/coredev/api.pid
echo "#################################################"