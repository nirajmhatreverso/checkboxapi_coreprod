#!/bin/bash

 /usr/bin/python3.9 /home/checkboxadmin/scripts/coreprod/manage.py runserver 0.0.0.0:9000 > /home/checkboxadmin/scripts/coreprod/log/django_app.log 2>&1 & echo $! > /home/checkboxadmin/scripts/coreprod/api.pid

echo "################PROCESS ID #######################" 
 cat /home/checkboxadmin/scripts/coreprod/api.pid
echo "#################################################"