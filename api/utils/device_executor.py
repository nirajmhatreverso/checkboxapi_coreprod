from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import logging

from .file_utils import clean_text, replace_new_line

logger = logging.getLogger('cmts_api')


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
 