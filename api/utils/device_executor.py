from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import logging
import time
import re
import telnetlib
from .file_utils import clean_text, replace_new_line, replace_variables,replace_ivariables
from .db import get_nested_command_configuration_by_id
logger = logging.getLogger('cmts_api')
strict_error_chk = False

def execute_device_db_commands() -> list:
    logger.info(f"execute device db successfully...")
    

def _execute_generic_telnet(
    device: dict,
    commands: list,
    filename: str,
    prompt_pattern: str,
    line_separator: str,
    enable_cmd: str,
) -> list:
    """
    Raw telnetlib handler for ZTE C320 OLT (generic_telnet devices)
    """
    outputs = []
    host = device.get('host', 'unknown')
    port = device.get('port', 23)
    username = device.get('username', '')
    password = device.get('password', '')
    secret = device.get('secret', '')
    timeout = device.get('conn_timeout', 60)
    logger.info(f"prompt_pattern:{prompt_pattern}")
    # Use passed prompt_pattern or fallback to ZTE default
    prompt = prompt_pattern if prompt_pattern else r"ZXAN[>#]"

    def read_until_prompt(tn, pattern, timeout=30):
        """Read channel until regex pattern is found or timeout"""
        output = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                chunk = tn.read_very_eager()
                if chunk:
                    output += chunk
                    decoded = output.decode("utf-8", errors="ignore")
                    if re.search(pattern, decoded):
                        break
            except Exception:
                pass
            time.sleep(0.2)
        result = output.decode("utf-8", errors="ignore")
        logger.debug(f"[{host}] Read: {result}")
        return result

    with open(filename, 'w', encoding='utf-8') as f:
        try:
            logger.info(f"Connecting to {host}:{port} via raw Telnet")
            tn = telnetlib.Telnet(host, port, timeout=timeout)

            # -- Login sequence --------------------------------------------
            read_until_prompt(tn, r"Username:", timeout=30)
            logger.info(f"[{host}] Got Username prompt")
            tn.write(username.encode() + b"\n")

            read_until_prompt(tn, r"Password:", timeout=15)
            logger.info(f"[{host}] Got Password prompt")
            tn.write(password.encode() + b"\n")

            # Wait for device prompt after login
            out = read_until_prompt(tn, prompt, timeout=20)
            if not re.search(prompt, out):
                raise Exception(f"Login failed — prompt not detected. Got: {out}")
            logger.info(f"[{host}] Logged in successfully")

            # -- Enable mode -----------------------------------------------
            if enable_cmd:
                tn.write(enable_cmd.encode() + b"\n")
                out = read_until_prompt(tn, r"Password:|#", timeout=10)
                if "Password:" in out:
                    logger.info("entering enable mode password")
                    tn.write(secret.encode() + b"\n")
                    read_until_prompt(tn, r"#", timeout=10)
                logger.info(f"[{host}] Entered enable mode")

            # Disable paging so output is not truncated
            tn.write(b"terminal length 0\n")
            read_until_prompt(tn, prompt, timeout=10)

            # -- Execute commands ------------------------------------------
            for cmd in commands:
                logger.info(f"[{host}] Executing: {cmd}")
                tn.write(cmd.encode() + b"\n")
                output = read_until_prompt(tn, prompt, timeout=60)

                cleaned = clean_text(replace_new_line(output, line_separator))
                outputs.append(cleaned)
                f.write(cleaned)
                f.write("\n############################\n")

            tn.write(b"exit\n")
            tn.close()
            logger.info(f"[{host}] Commands executed successfully")

        except Exception as e:
            msg = f"Unexpected error on {host}: {str(e)}"
            logger.exception(msg)
            outputs = [{"error": "Execution failed", "details": str(e)}]
            f.write(str(outputs) + "\n#######ERROR#######\n")
            raise

    return outputs


def execute_device_commands(
    device: dict,
    commands: list,
    filename: str,
    prompt_pattern: str,
    line_separator: str,
    enable_cmd: str,
    is_olt: bool = False,
    use_telnet: bool = False
) -> list:
    """
    Generic command execution function for both CMTS and OLT (SSH/Telnet)
    """
    outputs = []
    host = device.get('host', 'unknown')

    with open(filename, 'w', encoding='utf-8') as f:
        try:
            with ConnectHandler(**device) as conn:
                logger.info(f"Connected to {host} ({'Telnet' if use_telnet else 'SSH'})")
                if enable_cmd:
                    # Try to enter enable mode (not all devices/OLTs need or support it)
                    try:
                        conn.enable(cmd=enable_cmd)
                        logger.info(f"Entered enable mode on {host}")
                    except Exception as e:
                        if not is_olt:  # OLTs often don't need/want enable
                            logger.warning(f"Enable mode failed on {host}: {e}")

                for cmd in commands:
                    logger.info(f"Executing: {cmd}")
                    output = conn.send_command(
                        cmd,
                        expect_string=prompt_pattern,
                        read_timeout=60,
                        delay_factor=3,
                        strip_prompt=False,
                        strip_command=False
                    )

                    cleaned = clean_text(replace_new_line(output, line_separator))
                    outputs.append(cleaned)

                    f.write(cleaned)
                    f.write("\n############################\n")

            logger.info(f"Commands executed successfully on {host}")

        except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
            error_type = type(e).__name__
            msg = f"{error_type}: Connection failed - {str(e)}"
            logger.error(msg)
            outputs = [{"error": "Connection failed", "details": str(e)}]
            f.write(str(outputs) + "\n#######ERROR#######\n")
            raise

        except Exception as e:
            msg = f"Unexpected error on {host}: {str(e)}"
            logger.exception(msg)
            outputs = [{"error": "Execution failed", "details": str(e)}]
            f.write(str(outputs) + "\n#######ERROR#######\n")
            raise

    return outputs


def split_by_error(outputs, error_patterns):
    """
    Returns tuple of two lists:
    - successful_outputs
    - failed_outputs: list of (output, matched_error) tuples
    """
    error_set = {err.lower().strip() for err in error_patterns}
    success = []
    failed = []
    
    for output in outputs:
        cleaned = output.lower().strip()
        matched = next((err for err in error_set if err in cleaned), None)
        
        if matched:
            failed.append((output, matched))
        else:
            success.append(output)
            
    return success, failed
    
# Convert to bytes safely
def safe_to_bytes(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":")   # compact
        ).encode("utf-8")
    try:
        return str(value).encode("utf-8")
    except Exception:
        return b"[cannot convert to bytes]"
    
def execute_device_commands_with_template(template_name: str, 
                                          parameters: dict, 
                                          filename: str, 
                                          commands_dict: list, 
                                          host: str,
                                          device: dict,
                                           ) -> list:
    """
    Executes commands based on a template and parameters.
    This is a placeholder function. The actual implementation would depend on how templates are defined and used.
    """
    logger.info(f"Executing commands for template '{template_name}' on {host} with parameters {parameters}")
    outputs = []
    command_info = commands_dict['commands']
    template_info = commands_dict['template']
    use_telnet= template_info['login_type']
    logger.info(f"login type: {use_telnet}")
    enable_cmd=template_info['enable_custom']
    host = device.get('host', 'unknown')
    with open(filename, 'w', encoding='utf-8') as f:
        try:
            with ConnectHandler(**device) as conn:
                logger.info(f"Executing commands for command_info '{command_info}' on {host} with template_info {template_info}")    
                logger.info(f"Connected to {host} ({use_telnet})")
                if enable_cmd:
                    # Try to enter enable mode (not all devices/OLTs need or support it)
                    try:
                        conn.enable(cmd=enable_cmd)
                        logger.info(f"Entered enable mode on {host}")

                    except Exception as e:
                        if not enable_cmd:  # OLTs often don't need/want enable
                            logger.warning(f"Enable mode failed on {host}: {e}")

                for cmd_dict in command_info:
                    cmd = cmd_dict['commands']
                    cmd = replace_variables(str(cmd), parameters)
                    success_response_pattern = cmd_dict['success_response_pattern']
                    error_response_pattern = cmd_dict['error_response_pattern']
                    success_response = cmd_dict['success_response']
                    error_response = cmd_dict['error_response']
                    ns_flag = cmd_dict['ns_flag']
                    ns_template_id = cmd_dict['ns_template_id']
                    line_separator = template_info.get('line_separator', '\n')
                    logger.info(f"Executing: {cmd}")
                    output = conn.send_command(
                        cmd,
                        expect_string=rf'{success_response_pattern}',  # Adjust based on device prompt, or use a default r'#|>'
                        read_timeout=60,
                        delay_factor=10,
                        strip_prompt=False,
                        strip_command=False
                    )
                    cleaned = clean_text(replace_new_line(output, template_info.get('line_separator', '\n')))
                    if error_response_pattern and error_response_pattern.lower() in cleaned.lower():
                        if ns_flag == 1:
                            result_nested = get_nested_command_configuration_by_id( ns_template_id )
                            for item in result_nested:
                                ns_cmd = item['COMMANDS']
                                logger.info(f"command {ns_cmd}")
                                ns_error_pattern = item['ERROR_PATTERN']
                                logger.info(f"ns_error_pattern {ns_error_pattern}")
                                ns_success_pattern = item['SUCCESS_PATTERN']
                                logger.info(f"ns_success_pattern {ns_success_pattern}")
                                ns_cmd = replace_variables(str(ns_cmd), parameters)
                                if ns_error_pattern and ns_error_pattern.lower() in cleaned.lower():
                                    logger.info("nested command found to relpace")
                                    logger.info("command after replace:"+ns_cmd)
                                    output = conn.send_command(
                                        ns_cmd,
                                        expect_string=rf'{ns_success_pattern}',  # Adjust based on device prompt, or use a default r'#|>'
                                        read_timeout=60,
                                        delay_factor=10,
                                        strip_prompt=False,
                                        strip_command=False
                                    )
                                    cleaned = clean_text(replace_new_line(output, line_separator))
                                    break  #Exit loop after execution
                                else:
                                    logger.info("check next nested command pattern not found")
                        else:
                            raise Exception(cmd+":"+output)
                    if success_response_pattern and success_response_pattern.lower() not in cleaned.lower():
                        logger.debug(success_response)
                    outputs.append(cleaned)

                    f.write(cleaned)
                    f.write("\n############################\n")

            logger.info(f"Commands executed successfully on {host}")

        except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
            error_type = type(e).__name__
            msg = f"{error_type}: Connection failed - {str(e)}"
            logger.error(msg)
            outputs = [{"error": "Connection failed", "details": str(e)}]
            f.write(str(outputs) + "\n#######ERROR#######\n")
            raise

        except Exception as e:
            msg = f"Unexpected error on {host}: {str(e)}"
            logger.exception(msg)
            outputs = [{"error": "Execution failed", "details": str(e)}]
            f.write(str(outputs) + "\n#######ERROR#######\n")
            raise


    # For demonstration, we'll just format the commands with the parameters
    #formatted_commands = [cmd.format(**parameters) for cmd in command_info]
    
    # Here you would retrieve device info from the template and call execute_device_commands
    # For now, we'll just log the formatted commands and return them
    logger.info(f"Formatted commands for template '{template_name}': {command_info}")
    
    # You would replace the following line with actual device execution logic
    return outputs


def execute_device_commands_raw_telnet_with_template(template_name: str, 
                                          parameters: dict, 
                                          filename: str, 
                                          commands_dict: list, 
                                          host: str,
                                          device: dict,)->list:
    """
    Executes commands based on a template and parameters.
    This is a placeholder function. The actual implementation would depend on how templates are defined and used.
    """
    logger.info(f"Executing commands for template '{template_name}' on {host} with parameters {parameters}")
    outputs = []
    command_info = commands_dict['commands']
    template_info = commands_dict['template']
    use_telnet= template_info['login_type']
    enable_cmd=template_info['enable_custom']
    rw_telnet_username_pattern="Username:"
    rw_telnet_password_pattern="Password:"
    rw_enable_password_pattern="Password:|#"
    rw_after_enable_password_pattern="#"
    """
    Raw telnetlib handler for ZTE C320 OLT (generic_telnet devices)
    """
    outputs = []
    host = device.get('host', 'unknown')
    port = device.get('port', 23)
    username = device.get('username', '')
    password = device.get('password', '')
    secret = device.get('secret', '')
    timeout = template_info['timeout']
    
    # Use passed prompt_pattern or fallback to ZTE default
    prompt = template_info['template_expect_str'] if template_info['template_expect_str'] else command_info[0]['success_response_pattern']
    logger.info(f"prompt_pattern:{prompt}")
    def read_until_prompt(tn, pattern, timeout):
        """Read channel until regex pattern is found or timeout"""
        output = b""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                chunk = tn.read_very_eager()
                if chunk:
                    output += chunk
                    decoded = output.decode("utf-8", errors="ignore")
                    if re.search(pattern, decoded):
                        break
            except EOFError:
                logger.warning(f"[{host}] EOFError: device closed the connection")
                break
            except (BrokenPipeError, OSError) as e:
                logger.warning(f"[{host}] Pipe error during read: {e}")
                break
            except Exception:
                pass
            time.sleep(0.2)
        result = output.decode("utf-8", errors="ignore")
        logger.debug(f"[{host}] Read: {result}")
        return result

    with open(filename, 'w', encoding='utf-8') as f:
        logger.debug(f"Executing commands for command_info '{command_info}' on {host} with template_info {template_info}")    
        logger.info(f"Connected to {host} {use_telnet}")
        try:
            logger.info(f"Connecting to {host}:{port} via raw Telnet")
            tn = telnetlib.Telnet(host, port, timeout=timeout)
            
            # -- Login sequence --------------------------------------------
            read_until_prompt(tn, rf"{rw_telnet_username_pattern}", timeout)
            logger.info(f"[{host}] Got Username prompt")
            tn.write(username.encode() + b"\n")

            read_until_prompt(tn, rf"{rw_telnet_password_pattern}", timeout)
            logger.info(f"[{host}] Got Password prompt")
            tn.write(password.encode() + b"\n")

            # Wait for device prompt after login
            out = read_until_prompt(tn, prompt, timeout)
            if not re.search(prompt, out):
                raise Exception(f"Login failed — prompt not detected. Got: {out}")
            logger.info(f"[{host}] Logged in successfully")
            
            # -- Enable mode -----------------------------------------------
            if enable_cmd:
                tn.write(enable_cmd.encode() + b"\n")
                out = read_until_prompt(tn, rf"{rw_enable_password_pattern}", timeout)
                if "Password:" in out:
                    logger.info("entering enable mode password")
                    tn.write(secret.encode() + b"\n")
                    read_until_prompt(tn, rf"{rw_after_enable_password_pattern}", timeout)
                logger.info(f"[{host}] Entered enable mode")

            # Disable paging so output is not truncated
            tn.write(b"terminal length 0\n")
            read_until_prompt(tn, prompt, timeout)
            
            
            # -- Execute commands ------------------------------------------
            for cmd_dict in command_info:
                #logger.debug(f"[{host}] Executing: {cmd_dict}")
                error_response_pattern = cmd_dict['error_response_pattern']
                success_response_pattern = cmd_dict['success_response_pattern']
                success_response = cmd_dict['success_response']
                error_response = cmd_dict['error_response']
                ns_flag = cmd_dict['ns_flag']
                ns_template_id = cmd_dict['ns_template_id']
                line_separator = template_info.get('line_separator', '\n')
                logger.info(cmd_dict['commands'].encode() + b"\n")
                cmd = cmd_dict['commands']
                cmd = replace_variables(str(cmd), parameters)
                logger.info("command after replace:"+cmd)
                tn.write(cmd.encode() + b"\n")
                output = read_until_prompt(tn, prompt, timeout)
                cleaned = clean_text(replace_new_line(output, line_separator))
                if strict_error_chk:
                    if error_response_pattern and error_response_pattern.lower() in cleaned.lower():
                        logger.info(f"error dected {error_response_pattern}")
                        if ns_flag == 1:
                            logger.info(f"ns_flag :{ns_flag}")
                            result_nested = get_nested_command_configuration_by_id( ns_template_id )
                            for item in result_nested:
                                ns_cmd = item['COMMANDS']
                                logger.info(f"command {ns_cmd}")
                                ns_error_pattern = item ['ERROR_PATTERN']
                                logger.info(f"ns_error_pattern {ns_error_pattern}")
                                ns_success_pattern = item ['SUCCESS_PATTERN']
                                logger.info(f"ns_success_pattern {ns_success_pattern}")
                                ns_cmd = replace_variables(str(ns_cmd), parameters)
                                if ns_error_pattern and ns_error_pattern.lower() in cleaned.lower():
                                    logger.info("nested command found to relpace")
                                    logger.info("command after replace:"+ns_cmd)
                                    tn.write(ns_cmd.encode() + b"\n")
                                    output = read_until_prompt(tn, ns_success_pattern, timeout)
                                    cleaned = clean_text(replace_new_line(output, line_separator))
                                    logger.info("command executed:"+ns_cmd)
                                    break  # ? Exit loop after execution
                                else:
                                    logger.info("check next nested command pattern not found")
                        else:
                            raise Exception(cmd+":"+output)
                logger.info("strict check block ended")
                if success_response_pattern and success_response_pattern.lower() not in cleaned.lower():
                    logger.debug(success_response)
                outputs.append(cleaned)
                f.write(cmd+" "+cleaned)
                f.write("\n############################\n")

            tn.write(b"exit\n")
            logger.info("closing connection")
            tn.close()
            logger.info(f"[{host}] Commands executed successfully")
        except (BrokenPipeError, OSError) as be:
            raise Exception(f"[{host}] Connection lost while sending command - please check commands / interface: {be}")
        except Exception as e:
            msg = f"Unexpected error on {host}: {str(e)}"
            logger.exception(msg)
            outputs = [{"error": "Execution failed", "details": str(e)}]
            f.write(str(outputs) + "\n#######ERROR#######\n")
            raise

    return outputs