from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from datetime import datetime
from pathlib import Path
import logging

from .utils.logging_config import setup_logging
from .utils.file_utils import create_unique_file, read_file_to_list
from .utils.device_executor import execute_device_commands,split_by_error,safe_to_bytes
from .utils.db import insert_onu_activity_log

logger = setup_logging(debug=False)  # change to True in development

ALLOWED_LOGIN_TYPES = {"ssh", "telnet", "olt_ssh", "olt_telnet"}

ERROR_CHECK = [
    "error! please add the onu offline configuration first!!",
    "There no exist this srvprofile!",
    "input detected at",
    "There no exist this lineprofile",
    "error! please add the onu offline configuration first!!",
    ""
]

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / "tmp"


class InfoAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        logger.info("GET /info hit")
        return Response({
            "cmts_device": {
                "host": "IP address",
                "device_type": "cisco_ios_telnet | cisco_xe | linux | huawei | ...",
                "username": "username",
                "password": "password",
                "secret": "enable password (if required)",
                "global_delay_factor": 2,
                "session_log": "optional session log path",
                "port": 23  # for telnet, 22 for ssh
            },
            "commands": [
                "show version",
                "show running-config"
            ],
            "enable_custom": "enable",
            "login_type": "ssh | telnet | olt_ssh | olt_telnet",
            "regexPattern": r"[>#]",
            "lineSeperator": "@@@@@"
        }, status=status.HTTP_200_OK)


class infoAPIDBLogView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        logger.info("GET /info hit")
        return Response({
            "onu_activity_name": "CONFIGURE",
            "onu_command": "OMCI/CLI/API",
            "user_name": "SAMEERSWAIN@GMAIL.COM",
            "olt_ip": "172.16.10.55",
            "onu_serial": "OVTGBB6CB610",
            "username": "user123(PPPOE)",
            "password": "pass456(PPPOE)",
            "service_name": "service_name(PPPOE)",
            "stat_ip": "192.168.1.101(TAL)",
            "ip_address": "192.168.1.101(TAL)",
            "mask_address": "255.255.255.0(TAL)",
            "protocol_type": "PPPOE/TAL",
            "onu_type": "HG8245H",
            "dns_one": "dns_one",
            "dns_two": "dns_two",
            "request": "base64",
            "onu_response": "some binary response here",
            "auto_commit": "true"
        }, status=status.HTTP_200_OK)


class ExecuteCommandsAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"POST /execute from {client_ip}")

        try:
            data = request.data
            cmts_device = data.get("cmts_device")
            commands = data.get("commands")
            enable_custom = data.get("enable_custom", "enable")
            login_type = data.get("login_type", "ssh").lower()
            regex_pattern = data.get("regexPattern", r"[>#]")
            line_separator = data.get("lineSeperator", "@@@@@")

            if not cmts_device or not commands:
                return Response({"error": "Missing cmts_device or commands"}, status=400)

            if not isinstance(commands, list) or not all(isinstance(c, str) for c in commands):
                return Response({"error": "commands must be list of strings"}, status=400)

            if login_type not in ALLOWED_LOGIN_TYPES:
                return Response({
                    "error": f"Invalid login_type. Allowed: {', '.join(ALLOWED_LOGIN_TYPES)}"
                }, status=400)

            # Prepare file
            tmp_file = create_unique_file(TMP_DIR, prefix="exec_", extension=".tmp")

            # Choose execution strategy
            is_olt = "olt" in login_type
            use_telnet = "telnet" in login_type

            outputs = execute_device_commands(
                device=cmts_device,
                commands=commands,
                filename=tmp_file,
                prompt_pattern=regex_pattern,
                line_separator=line_separator,
                enable_cmd=enable_custom,
                is_olt=is_olt,
                use_telnet=use_telnet
            )
            
            # it will return success & error statements
            success, failed = split_by_error(outputs, ERROR_CHECK)
            

            file_content = read_file_to_list(tmp_file)

            return Response({
                "status": "success",
                "host": cmts_device.get("host", "unknown"),
                "login_type": login_type,
                "command_count": len(commands),
                "outputs": outputs,
                "fileName": tmp_file,
                "successCommands" : success,
                "failedCommands" : failed,
                "file_preview": file_content[:30]  # first 30 lines for debug/info
            }, status=200)

        except Exception as e:
            logger.exception("Critical error in execute endpoint")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=500)

class DbLogSaveAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"POST /db logs from {client_ip}")
        try:    
            logger.info(f"POST /insert operation logs from")
            data = request.data
            onu_activity_ts = data.get("onu_activity_ts")
            onu_activity_name = data.get("onu_activity_name")
            onu_command = data.get("onu_command")
            user_name = data.get("user_name")
            olt_ip = data.get("olt_ip")
            onu_serial = data.get("onu_serial")
            username = data.get("username")
            password = data.get("password")
            service_name = data.get("service_name")
            stat_ip = data.get("stat_ip")
            ip_address = data.get("ip_address")
            mask_address = data.get("mask_address")
            protocol_type = data.get("protocol_type")
            onu_type = data.get("onu_type")
            dns_one = data.get("dns_one")
            dns_two = data.get("dns_two")
            request = data.get("request")
            onu_response = data.get("onu_response")
            auto_commit = data.get("auto_commit")
            
            logger.info(f"logging activity :{onu_activity_name}")
            logger.info(f"user_name :{user_name}")
            logger.info(f"onu_serial :{onu_serial}")
            request_bytes = safe_to_bytes(request)
            onu_response_bytes = safe_to_bytes(onu_response)
            
            new_id = insert_onu_activity_log(
            onu_activity_ts=datetime.now(),
            onu_activity_name=onu_activity_name,
            onu_command=onu_command,
            user_name=user_name,
            olt_ip=olt_ip,
            onu_serial=onu_serial,
            username=username,
            password=password,
            service_name=service_name,
            stat_ip=stat_ip,
            ip_address=ip_address,
            mask_address=mask_address,
            protocol_type=protocol_type,
            onu_type=onu_type,
            dns_one=dns_one,
            dns_two=dns_two,
            request=request_bytes,
            onu_response=onu_response_bytes,
            auto_commit=True)
            msg = f"log inserted with activity id : {new_id}"
            return Response({
                "status": "success",
                "message":msg
            }, status=200)
        except Exception as e:
            logger.exception("Critical error in execute endpoint")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=500)
