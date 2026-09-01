import os
import django

from netagent.models import PyaTmpMaster
from netagent.serializers import TemplateWithCommandsSerializer

# Configure Django settings before importing REST framework
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coreuat.settings')
django.setup()

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from datetime import datetime
from pathlib import Path
import logging

from .utils.logging_config import setup_logging
from .utils.file_utils import create_unique_file, read_file_to_list, log_pretty
from .utils.device_executor import execute_device_commands,split_by_error, safe_to_bytes, execute_device_commands_with_template, _execute_generic_telnet, execute_device_commands_raw_telnet_with_template
from .utils.db import insert_onu_activity_log,get_command_with_template
#get_command_with_template,get_command_configuration_by_id,get_template_by_id,upsert_template_mst, upsert_command_configuration
# ORM-based replacements for all config/template operations
from .views_orm import (
    orm_get_command_configuration_by_id as get_command_configuration_by_id,
    orm_get_template_by_id             as get_template_by_id,
    orm_upsert_command_configuration   as upsert_command_configuration,
    orm_upsert_template_mst            as upsert_template_mst,
)

logger = setup_logging(debug=True)  # change to True in development

ALLOWED_LOGIN_TYPES = {"ssh", "telnet", "olt_ssh", "olt_telnet"}

ERROR_CHECK = [
    "error! please add the onu offline configuration first!!",
    "There no exist this srvprofile!",
    "input detected at",
    "There no exist this lineprofile",
    "error! please add the onu offline configuration first!!",
    "code",
    "invalid",
    "Error"
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

class ExecuteCommandsWithTemplateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"POST /ExecuteCommandsWithTemplateAPIView from {client_ip}")
        outputs = []
        tmp_file = None
        file_content = []
        onu_activity_name = "config"
        onu_command = "omci"
        user_name = None
        olt_ip = None
        onu_serial = None
        username = None
        password = None
        service_name = None
        stat_ip = None
        ip_address = None
        mask_address = None
        protocol_type = None
        onu_type = None
        dns_one = None
        dns_two = None
        userid = None
        request_ = None
        onu_response = None
        try:
            data = request.data
            print(type(data))
            logger.info(f"Request data: {request.data}")
            template_name = data.get("template_name")
            parameters = data.get("parameters", {})
            host_name = parameters["host_ip"]
            if not template_name:
                return Response({"error": "Missing template_name"}, status=400)
            if not host_name:
                return Response({"error": "Missing host_name"}, status=400)
            
            #Fields for logging
            onu_activity_name = "config"
            onu_command = "omci"
            user_name = parameters.get("user_name")
            olt_ip = parameters.get("host_ip") or None
            onu_serial = parameters.get("SERIAL") or None
            username = parameters.get("ONU_USER_NAME")
            password = parameters.get("ONU_PASSWORD")
            service_name = parameters.get("ONU_SERVICE_NAME") or None  
            stat_ip = parameters.get("TAL_GETWAY") or None
            ip_address = parameters.get("TAL_IP_ADDRESS") or None
            mask_address = parameters.get("TAL_SUBNET_MASK") or None
            protocol_type = parameters.get("connection_type") or None
            onu_type = parameters.get("ONU_TYPE") or None
            dns_one = parameters.get("TAL_DNS_ONE") or None
            dns_two = parameters.get("TAL_DNS_TWO") or None
            userid = parameters.get("USER_ID") or None
            request_ = None #CURRENTLY BLANK
            # Prepare file
            tmp_file = create_unique_file(TMP_DIR, prefix="exec_cmd_temp_", extension=".tmp")
            onu_response = tmp_file

            # Call your get_command_with_template function here
            commands = get_command_with_template(template_name)
            logger.debug(f" result type {type(commands)}")
            logger.info(f"Retrieved commands for template : {template_name}: {commands}")
            if not commands:
                return Response({"error": f"not found commands for template_{template_name}"}, status=400)
            device = create_device_config_json(commands, host_name, session_log=tmp_file)  
            # Execute commands based on template
            
            if commands['template']['login_type'] == 'ssh' or commands['template']['login_type'] == 'telnet':
                outputs = execute_device_commands_with_template(
                    template_name=template_name,
                    parameters=parameters,
                    filename=tmp_file,
                    commands_dict=commands,
                    host=host_name,
                    device=device)
            elif commands['template']['login_type'] == 'custom_telnet':    
                outputs = execute_device_commands_raw_telnet_with_template(
                    template_name=template_name,
                    parameters=parameters,
                    filename=tmp_file,
                    commands_dict=commands,
                    host=host_name,
                    device=device)
                    
            logger.info(f"reading file : {file_content}")
            file_content = read_file_to_list(tmp_file)
            # it will return success & error statements
            success, failed = split_by_error(file_content, ERROR_CHECK)

            # Logging only when successful execution (no failures)
            logger.info(f"log insertion to db")
            if 0 == 0:
                try:
                    insert_onu_activity_log(
                onu_activity_ts=datetime.now(),
                onu_activity_name=onu_activity_name,
                onu_command=onu_command,
                user_name=userid,
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
                request=request_,
                onu_response=onu_response,
                auto_commit=True)
                
                except Exception as log_error:
                    logger.error(f"Logging failed: {log_error}")
            logger.info(f"log insertion to db completed")
            
            return Response({
                "status": "success" if not failed else "Error",
                "template_name": template_name,
                "outputs": outputs,
                "fileName": tmp_file,
                "successCommands" : success,
                "failedCommands" : failed,
                "file_preview": file_content[:100]  # first 100 lines for debug/info
            }, status=200)

        except Exception as e:
            logger.info(f"log insertion to db")
            if 0 == 0:
                try:
                    insert_onu_activity_log(
                        onu_activity_ts=datetime.now(),
                        onu_activity_name=onu_activity_name,
                        onu_command=onu_command,
                        user_name=userid,
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
                        request=request_,
                        onu_response=onu_response,
                        auto_commit=True)
                        
                except Exception as log_error:
                    logger.error(f"Logging failed: {log_error}")
            logger.info(f"log insertion to db completed")
            logger.exception("Critical error in ExecuteCommandsWithTemplateAPIView endpoint")
            return Response({
                "status": "error",
                "message": str(e),
                "outputs": outputs,
                "fileName": tmp_file,
                "file_preview": file_content[:100] 
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


class GetCommandWithTemplateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"POST /command-template from {client_ip}")
        
        try:
            data = request.data
            template_name = data.get("template_name")
            logger.info(f"template_name {template_name}")
            if not template_name:
                return Response(
                    {"error": "Missing template_name parameter"},
                    status=400
                )
            
            # Call your get_command_with_template function here
            commands = get_command_with_template(template_name)
            return Response({
                "status": "success",
                "template_name": template_name,
                "commands": commands
            }, status=200)
            
        except Exception as e:
            logger.exception("Error in get_command_with_template endpoint")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=500)
            
            
class GetCommandConfigurationAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"GET /command-configuration from {client_ip}")
        try:
            data = request.data
            config_id = data.get("id")
            
            if not config_id:
                return Response({"error": "Missing id parameter"}, status=400)
            
            logger.info(f"Fetching configuration for id: {config_id}")
            
            configuration = get_command_configuration_by_id(config_id)
            
            if not configuration:
                return Response({"error": "Configuration not found"}, status=404)
            
            return Response({
                "status": "success",
                "configuration": configuration
            }, status=200)
        except Exception as e:
            logger.exception("Critical error in get-command-configuration endpoint")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=500)

class GetTemplateByIdAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        
        try:
            data = request.data
            template_id = data.get("id")
            logger.info(f"GET /template/{template_id} from {client_ip}")
            template = get_template_by_id(template_id)
            if not template:
                return Response({
                    "status": "error",
                    "message": f"Template with id {template_id} not found"
                }, status=404)
            
            logger.info(f"Retrieved template: {template_id}")
            
            return Response({
                "status": "success",
                "data": template
            }, status=200)
            
        except Exception as e:
            logger.exception("Critical error in get template endpoint")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=500)


class UpsertTemplateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"POST /upsert-template from {client_ip}")
        
        try:
            data = request.data
            template_name = data.get("template_name")
            login_type = data.get("login_type")
            username = data.get("username")
            password = data.get("password")
            secret = data.get("secret")
            global_delay_factor = data.get("global_delay_factor")
            port = data.get("port")
            enable_custom = data.get("enable_custom")
            line_seperator = data.get("line_seperator")
            host = data.get("host")
            device_type = data.get("device_type")
            
            # Validate required fields
            if not template_name or not isinstance(template_name, str) or len(template_name.strip()) == 0:
                return Response(
                    {"error": "template_name is required and must be a non-empty string"},
                    status=400
                )
            
            if not login_type or not isinstance(login_type, str):
                return Response(
                    {"error": "login_type is required and must be a string"},
                    status=400
                )
            
            if not username or not isinstance(username, str):
                return Response(
                    {"error": "username is required and must be a string"},
                    status=400
                )
            
            if not password or not isinstance(password, str):
                return Response(
                    {"error": "password is required and must be a string"},
                    status=400
                )
            
            logger.info(f"Upserting template: {template_name}")
            
            result = upsert_template_mst(
                template_name=template_name,
                login_type=login_type,
                username=username,
                password=password,
                secret=secret,
                global_delay_factor=global_delay_factor,
                port=port,
                enable_custom=enable_custom,
                line_seperator=line_seperator,
                host=host,
                device_type=device_type
            )
            
            return Response({
                "status": "success",
                "message": "Template upserted successfully",
                "data": result
            }, status=200)
            
        except Exception as e:
            logger.exception("Critical error in upsert-template endpoint")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=500)

class UpsertCommandConfigurationAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"POST /upsert-command-configuration from {client_ip}")
        
        try:
            data = request.data
            command_name = data.get("command_name")
            template_id = data.get("template_id")
            commands = data.get("commands")
            success_response = data.get("success_response")
            error_response = data.get("error_response")
            command_purpose = data.get("command_purpose")
            error_response_pattern = data.get("error_response_pattern")
            success_response_pattern = data.get("success_response_pattern")
            device_name = data.get("device_name")
            
            # Validate required fields
            if not command_name or not isinstance(command_name, str) or len(command_name.strip()) == 0:
                return Response(
                    {"error": "command_name is required and must be a non-empty string"},
                    status=400
                )
            
            if not template_id or not isinstance(template_id, int):
                return Response(
                    {"error": "template_id is required and must be an integer"},
                    status=400
                )
            
            if not commands or not isinstance(commands, str) or len(commands.strip()) == 0:
                return Response(
                    {"error": "commands is required and must be a non-empty string"},
                    status=400
                )
            
            logger.info(f"Upserting command configuration: {command_name}")
            
            result = upsert_command_configuration(
                command_name=command_name,
                template_id=template_id,
                commands=commands,
                success_response=success_response,
                error_response=error_response,
                command_purpose=command_purpose,
                error_resp_pattern=error_response_pattern,
                success_resp_pattern=success_response_pattern,
                device_name=device_name
            )
            
            return Response({
                "status": "success",
                "message": "Command configuration upserted successfully",
                "data": result
            }, status=200)
            
        except Exception as e:
            logger.exception("Critical error in upsert-command-configuration endpoint")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=500)            
        

def create_device_config_json(result, hostname, session_log):
    """
    Creates a sample device configuration JSON file for testing.
    """
    template = result.get('template', {})
    sample_config = {
        "device": {
            "host": hostname,
            "device_type": template.get('device_type', 'NA'),
            "username": template.get('username', 'NA'),
            "password": template.get('password', 'NA'),
            "secret": template.get('secret', ''),
            "global_delay_factor": int(template.get('global_delay_factor', 2)),
            "session_log": session_log,
            "port": template.get('port', 23),
            "global_cmd_verify": False
        }
    }
    logger.info(f" sample_config: {sample_config}")
    return sample_config['device']



class GetCommandConfigAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Implementation for getting command configuration
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"POST /execute-generic-telnet from {client_ip}")
        try:
            data = request.data
            template_name = data.get("template_name")
            if not template_name:
                return Response(
                    {'error':'template_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            templates = PyaTmpMaster.objects.prefetch_related('temp').filter(template_id=template_name).all()
            if not templates:
                return Response(
                    {'error': 'Template not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
            template = templates.first()
            commands = template.temp.all().order_by('sequence')
        
            data = {
                "commands": commands,
                "template": template
            }
        
            serializer = TemplateWithCommandsSerializer(data)
            return Response(serializer.data)


        except Exception as e:
            logger.exception("Critical error in execute-generic-telnet endpoint")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=500)

class ExecuteGenericTelnetAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"POST /execute-generic-telnet from {client_ip}")

        try:
            data = request.data
            cmts_device = data.get("cmts_device")
            commands = data.get("commands")
            enable_custom = data.get("enable_custom", "enable")
            regex_pattern = data.get("regexPattern", r"ZXAN[>#]")
            line_separator = data.get("lineSeperator", "@@@@@")

            # -- Validation ------------------------------------------------
            if not cmts_device or not commands:
                return Response(
                    {"error": "Missing cmts_device or commands"},
                    status=400
                )

            if not isinstance(commands, list) or not all(isinstance(c, str) for c in commands):
                return Response(
                    {"error": "commands must be a list of strings"},
                    status=400
                )

            required_device_fields = ["host", "username", "password"]
            missing_fields = [f for f in required_device_fields if not cmts_device.get(f)]
            if missing_fields:
                return Response(
                    {"error": f"Missing device fields: {', '.join(missing_fields)}"},
                    status=400
                )

            # -- Prepare temp file -----------------------------------------
            tmp_file = create_unique_file(TMP_DIR, prefix="telnet_", extension=".tmp")

            # -- Execute ---------------------------------------------------
            outputs = _execute_generic_telnet(
                device=cmts_device,
                commands=commands,
                filename=tmp_file,
                prompt_pattern=regex_pattern,
                line_separator=line_separator,
                enable_cmd=enable_custom,
            )

            success, failed = split_by_error(outputs, ERROR_CHECK)
            file_content = read_file_to_list(tmp_file)

            return Response({
                "status": "success",
                "host": cmts_device.get("host", "unknown"),
                "login_type": "generic_telnet",
                "command_count": len(commands),
                "outputs": outputs,
                "fileName": tmp_file,
                "successCommands": success,
                "failedCommands": failed,
                "file_preview": file_content[:30]
            }, status=200)

        except Exception as e:
            logger.exception("Critical error in execute-generic-telnet endpoint")
            return Response({
                "status": "error",
                "message": str(e)
            }, status=500)
        

