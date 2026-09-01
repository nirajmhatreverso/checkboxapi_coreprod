# utils/db.py
import sys

import oracledb
from django.conf import settings
from contextlib import contextmanager
import logging
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
import binascii

from .logging_config import setup_logging

logger = setup_logging(debug=False)

template_master = settings.DATABASES['table']['template_master']
nested_configuration = settings.DATABASES['table']['nested_configuration']
command_configuration = settings.DATABASES['table']['command_configuration']
activity_log = settings.DATABASES['table']['activity_log']

@contextmanager
def get_oracle_connection():
    """Context manager for safe Oracle connection handling"""
    conn = None
    try:
        # Modern way - using service name (preferred)
        #oracledb.init_oracle_client()
        # Initialize Oracle client ONCE at module level (not inside the function)
        if sys.platform == "win32":
            oracledb.init_oracle_client(lib_dir=r"C:\instantclient-basic-windows\instantclient_23_0")
        else:
            oracledb.init_oracle_client()  # Linux: uses system-installed client
        logger.info(f"Oracle connection opened for platform {sys.platform}")
        conn = oracledb.connect(
            user=settings.DATABASES['oracle']['USER'],
            password=settings.DATABASES['oracle']['PASSWORD'],
            dsn=f"{settings.DATABASES['oracle']['HOST']}:{settings.DATABASES['oracle']['PORT']}/{settings.DATABASES['oracle']['NAME']}"
            # min=1, max=10, increment=1   ← you can add pool if needed
        )
        logger.debug("Oracle connection opened")
        yield conn
    except oracledb.Error as e:
        logger.error(f"Oracle connection failed: {e}")
        raise
    finally:
        if conn:
            try:
                conn.close()
                logger.debug("Oracle connection closed")
            except:
                pass


def get_oracle_connection_simple():
    oracledb.init_oracle_client()
    return oracledb.connect(
        user='reports',
        password='JMNRp578',
        dsn="172.20.20.24:1213/misdb",
        tcp_connect_timeout=30,
        retry_count=3,
        retry_delay=2
    )


def safe_raw(value):
    if value is None:
        return None
    if isinstance(value, str):
        return binascii.hexlify(value.encode()).decode()
    return value

def get_sequence_id(cursor, seq_name: str = "UAT_ONU_ACT_LOG_DETAILS_SEQ") -> int:
    """Standalone way to get next sequence value as int"""
    cursor.execute(f"SELECT {seq_name}.NEXTVAL FROM DUAL")
    return int(cursor.fetchone()[0])  # always returns NUMBER → safe to int()

def get_template_mst( cursor, template_name ):
    """ select data from pya_config_master """
    config_mst_query="""
        SELECT 
            LOGIN_TYPE,
            USERNAME,
            PASSWORD,
            TEMPLATE_ID,
            SECRET,
            GLOBAL_DELAY_FACTOR,
            PORT,
            ENABLE_CUSTOM,
            LINE_SEPERATOR,
            HOST,
            DEVICE_TYPE,
            TEMPLATE_NAME
        FROM {template_master}
        WHERE TEMPLATE_NAME = :template_name
    """.format(template_master=template_master)
    try:
        cursor.execute(config_mst_query, template_name=template_name)
        rows = cursor.fetchall()
        
        if not rows:
            raise ValueError(f"No templates found for TEMPLATE_NAME = {template_name!r}")

        logger.debug(f"Loaded {len(rows)} template(s) for '{template_name}'")
        return rows
        
    except Exception as e:
        logger.error(f"Failed to fetch templates '{template_name}': {e}")
        raise

def upsert_nested_command_configurations(
    template_id: int,
    commands: str,
    error_pattern: str = None,
    success_pattern: str = None,
    sequence: int = None
    ) -> int:
    """
    UPSERT (update or insert) a row in PYA_NESTEST_CONFIGURATION based on TEMPLATE_ID.    
    Returns: the TEMPLATE_ID (existing or newly created)
    """
    merge_sql = """
    MERGE INTO {nested_configuration} t
    USING (SELECT :template_id AS TEMPLATE_ID FROM dual) s
    ON (t.TEMPLATE_ID = s.TEMPLATE_ID)
        
    WHEN MATCHED THEN
    UPDATE SET
        COMMANDS          = :commands,
        ERROR_PATTERN     = :error_pattern,
        SUCCESS_PATTERN   = :success_pattern,
        SEQUENCE          = :sequence
                
    WHEN NOT MATCHED THEN
        INSERT (
        TEMPLATE_ID,
        COMMANDS,
        ERROR_PATTERN,
        SUCCESS_PATTERN,
        SEQUENCE
        )
        VALUES (
        :template_id,
        :commands,
        :error_pattern,
        :success_pattern,
        :sequence
        )
    """.format(nested_configuration=nested_configuration)
        
    with get_oracle_connection() as conn:
        cursor = conn.cursor()
        try:
            bind_vars = {
                'template_id': template_id,
                'commands': commands,
                'error_pattern': error_pattern,
                'success_pattern': success_pattern,
                'sequence': sequence,
            }
            _format_query_for_logging(merge_sql, bind_vars)
            cursor.execute(merge_sql, bind_vars)
            conn.commit()

            action = "Updated" if cursor.rowcount > 0 else "Inserted"
            logger.info(f"{action} nested configuration for TEMPLATE_ID = {template_id}")

            return template_id

        except Exception as e:
            logger.error(f"Upsert failed for nested configuration TEMPLATE_ID '{template_id}': {e}")
            raise

def upsert_template_mst(
    template_name: str,
    login_type: str,
    username: str,
    password: str,
    secret: str = None,
    global_delay_factor: int = None,
    port: int  = None,
    enable_custom: str = None,       # e.g. 0/1 or 'Y'/'N'
    line_seperator: str = None,            # note: typo in your column name?
    host: str = None,
    device_type: str = None
    ) -> int:
    """
    UPSERT (update or insert) a row in PYA_TMP_MASTER based on TEMPLATE_NAME.
    
    Returns: the TEMPLATE_ID (existing or newly created)
    """
    merge_sql = """
    MERGE INTO {template_master} t
    USING (SELECT :template_name AS TEMPLATE_NAME FROM dual) s
    ON (t.TEMPLATE_NAME = s.TEMPLATE_NAME)
    
    WHEN MATCHED THEN
        UPDATE SET
            LOGIN_TYPE           = :login_type,
            USERNAME             = :username,
            PASSWORD             = :password,
            SECRET               = :secret,
            GLOBAL_DELAY_FACTOR  = :global_delay_factor,
            PORT                 = :port,
            ENABLE_CUSTOM        = :enable_custom,
            LINE_SEPERATOR       = :line_seperator,
            HOST                 = :host,
            DEVICE_TYPE          = :device_type
            -- Add audit columns if they exist, e.g.:
            -- LAST_UPDATED = SYSDATE,
            -- UPDATED_BY   = USER
            
    WHEN NOT MATCHED THEN
        INSERT (
            
            LOGIN_TYPE,
            USERNAME,
            PASSWORD,
            SECRET,
            GLOBAL_DELAY_FACTOR,
            PORT,
            ENABLE_CUSTOM,
            LINE_SEPERATOR,
            HOST,
            DEVICE_TYPE,
            TEMPLATE_NAME
            -- CREATED_AT, CREATED_BY   -- if present
        )
        VALUES (
            :login_type,
            :username,
            :password,
            :secret,
            :global_delay_factor,
            :port,
            :enable_custom,
            :line_seperator,
            :host,
            :device_type,
            :template_name
        )
    """.format(template_master=template_master)
    with get_oracle_connection() as conn:
        cursor = conn.cursor()
        try:
            bind_vars = {
                'template_name': template_name,
                'login_type': login_type,
                'username': username,
                'password': password,
                'secret': secret,
                'global_delay_factor': global_delay_factor,
                'port': port,
                'enable_custom': enable_custom,
                'line_seperator': line_seperator,     # careful with spelling
                'host': host,
                'device_type': device_type,
            }
            _format_query_for_logging(merge_sql, bind_vars)
            cursor.execute(merge_sql, bind_vars)
            conn.commit()
            bind_vars1 = { 'tn' : template_name}
            # Retrieve the TEMPLATE_ID after the operation (most reliable way)
            cursor.execute(
                """
                SELECT TEMPLATE_ID 
                FROM {template_master} 
                WHERE TEMPLATE_NAME = :tn
                """,
                bind_vars1
            )
            template_id = cursor.fetchone()[0]

            action = "Updated" if cursor.rowcount > 0 else "Inserted"  # rowcount from MERGE
            logger.info(f"{action} template '{template_name}' TEMPLATE_ID = {template_id}")

            return template_id

        except Exception as e:
            logger.error(f"Upsert failed for template '{template_name}': {e}")
            raise

        
def get_command_configuration( cursor, command_name ):
    """ select data from pya_config_master """

    command_configuration = settings.DATABASES['table']['command_configuration']

    config_mst_query="""
        SELECT 
            CONFIG_ID,
            TEMPLATE_ID,
            COMMANDS,
            SUCCESS_RESPONSE,
            ERROR_RESPONSE,
            COMMAND_NAME,
            COMMAND_PURPOSE,
            ERROR_RESPONSE_PATTERN,
            SUCCESS_RESPONSE_PATTERN,
            DEVICE_NAME
        FROM {command_configuration}
        WHERE COMMAND_NAME = :command_name
    """.format(command_configuration=command_configuration)
    try:
        cursor.execute(config_mst_query, command_name=command_name)
        rows = cursor.fetchall()
        
        if not rows:
            raise ValueError(f"No commands found for command name = {command_name!r}")

        logger.debug(f"Loaded {len(rows)} commands(s) for '{command_name}'")
        return rows
        
    except Exception as e:
        logger.error(f"Failed to fetch command '{command_name}': {e}")
        raise

def _format_query_for_logging(sql: str, bind_vars: dict) -> str:
    """Format SQL with bind variables for logging purposes only."""
    formatted = sql
    for key, value in bind_vars.items():
        placeholder = f":{key}"
        if value is None:
            replacement = "NULL"
        elif isinstance(value, str):
            replacement = f"'{value}'"
        else:
            replacement = str(value)
        formatted = formatted.replace(placeholder, replacement)
        logger.debug(f"Formatted SQL: {formatted}")

def upsert_command_configuration(
    command_name: str,
    template_id: int,
    commands: str,
    success_response: str = None,
    error_response: str = None,
    command_purpose: str = None,
    error_resp_pattern: str = None,
    success_resp_pattern: str = None,
    device_name: str = None
) -> int:
    """
    Insert new command configuration or update existing one (UPSERT).
    
    Matching is done on COMMAND_NAME (assumed unique or primary/business key).
    
    Returns: the CONFIG_ID (newly inserted or existing)
    """
    merge_sql = """
    MERGE INTO {command_configuration} t
    USING (SELECT :command_name AS COMMAND_NAME FROM dual) s
    ON (t.COMMAND_NAME = s.COMMAND_NAME)
    
    WHEN MATCHED THEN
        UPDATE SET
            TEMPLATE_ID             = :template_id,
            COMMANDS                = :commands,
            SUCCESS_RESPONSE        = :success_response,
            ERROR_RESPONSE          = :error_response,
            COMMAND_PURPOSE         = :command_purpose,
            ERROR_RESPONSE_PATTERN  = :error_resp_pattern,
            SUCCESS_RESPONSE_PATTERN = :success_resp_pattern,
            DEVICE_NAME             = :device_name
            -- LAST_UPDATED = SYSDATE,   -- uncomment if you have audit column
            -- UPDATED_BY   = USER       -- optional
        WHERE t.COMMAND_NAME = :command_name  -- safety
            
    WHEN NOT MATCHED THEN
        INSERT (
            CONFIG_ID,
            TEMPLATE_ID,
            COMMANDS,
            SUCCESS_RESPONSE,
            ERROR_RESPONSE,
            COMMAND_NAME,
            COMMAND_PURPOSE,
            ERROR_RESPONSE_PATTERN,
            SUCCESS_RESPONSE_PATTERN,
            DEVICE_NAME
            -- CREATED_AT, CREATED_BY   -- if you have them
        )
        VALUES (
            PYA_COMMAND_CONFIG_SEQ.NEXTVAL,   -- assuming you have a sequence
            :template_id,
            :commands,
            :success_response,
            :error_response,
            :command_name,
            :command_purpose,
            :error_resp_pattern,
            :success_resp_pattern,
            :device_name
        )
    """.format(command_configuration=command_configuration)
    #logger.info(f"merge_sql : {merge_sql}")
    with get_oracle_connection() as conn:
        cursor = conn.cursor()
        try:
            bind_vars = {
            'command_name': command_name,
            'template_id': template_id,
            'commands': commands,
            'success_response': success_response,
            'error_response': error_response,
            'command_purpose': command_purpose,
            'error_resp_pattern': error_resp_pattern,
            'success_resp_pattern': success_resp_pattern,
            'device_name': device_name,
            }
            #formatted_sql = _format_query_for_logging(merge_sql, bind_vars)
            cursor.execute(merge_sql,bind_vars)
            # ── Get the CONFIG_ID after merge ────────────────────────────────
            # Option A: query it back (most reliable)
            bind_vars1 = { 'cmd_name' : command_name}
            conn.commit()
            merge_sql1 = """
                SELECT CONFIG_ID 
                FROM {command_configuration} 
                WHERE COMMAND_NAME = :cmd_name
                """.format(command_configuration=command_configuration)
            cursor.execute(merge_sql1,bind_vars1)
            #formatted_sql = _format_query_for_logging(merge_sql1, bind_vars1)
            config_id = cursor.fetchone()[0]
            logger.info(
                f"{'Updated' if cursor.rowcount > 0 else 'Inserted'} command configuration ")
            logger.info( f"for '{command_name}' CONFIG_ID = {config_id}")
            return config_id
        
        except Exception as e:
            logger.error(f"Upsert failed for command '{command_name}': {e}", exc_info=True)
            raise

def insert_onu_activity_log(
    onu_activity_ts: str,
    onu_activity_name: str,
    onu_command: str,
    user_name: str,
    olt_ip: str,
    onu_serial: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    service_name: Optional[str] = None,
    stat_ip: Optional[str] = None,
    ip_address: Optional[str] = None,
    mask_address: Optional[str] = None,
    protocol_type: Optional[str] = None,
    onu_type: Optional[str] = None,
    dns_one: Optional[str] = None,
    dns_two: Optional[str] = None,
    request: Optional[bytes] = None,
    onu_response: Optional[bytes] = None,
    auto_commit: bool = True
) -> int:
    """
    Insert a record into REPORTS.UAT_ONU_ACTIVITY_LOG_DETAILS
    Returns the generated ONU_ACTIVITY_LOG_ID (from sequence)
    """
    
    activity_log = settings.DATABASES['table']['activity_log']
    
    sql = """
    INSERT INTO {activity_log} (
        ONU_ACTIVITY_LOG_ID,
        ONU_ACTIVITY_NAME,
        ONU_COMMAND,
        USER_NAME,
        OLT_IP,
        ONU_SERIAL,
        USERNAME,
        PASSWORD,
        SERVICE_NAME,
        STAT_IP,
        IP_ADDRESS,
        MASK_ADDRESS,
        PROTOCOL_TYPE,
        ONU_TYPE,
        DNS_ONE,
        DNS_TWO,
        REQUEST,
        ONU_RESPONSE,
        ONU_ACTIVITY_TS
    ) VALUES (
        :seq,
        :onu_activity_name,
        :onu_command,
        :user_name,
        :olt_ip,
        :onu_serial,
        :username,
        :password,
        :service_name,
        :stat_ip,
        :ip_address,
        :mask_address,
        :protocol_type,
        :onu_type,
        :dns_one,
        :dns_two,
        :request,
        :onu_response,
        CURRENT_TIMESTAMP
    )
    """.format(activity_log=activity_log)
#    
    logger.info(f"""
        insert_onu_activity_log params:
        onu_activity_ts  = {datetime.now()}
        onu_activity_name= {onu_activity_name}
        onu_command      = {onu_command}
        user_name        = {user_name}
        olt_ip           = {olt_ip}
        onu_serial       = {onu_serial}
        username         = {username}
        password         = {password}
        service_name     = {service_name}
        stat_ip          = {stat_ip}
        ip_address       = {ip_address}
        mask_address     = {mask_address}
        protocol_type    = {protocol_type}
        onu_type         = {onu_type}
        dns_one          = {dns_one}
        dns_two          = {dns_two}
        onu_response     = {onu_response}
    """)
    logger.info(f"request {str(request)}")
    logger.info(f"onu_response {onu_response}")
    try:
        with get_oracle_connection() as conn:
            cursor = conn.cursor()
            
            onu_activity_ts = datetime.now(ZoneInfo("UTC"))
            logger.info(f"act ts: {onu_activity_ts}")
            # Important: prepare OUT variable
            #cursor.setinputsizes(new_id=oracledb.NUMBER)
            seq=get_sequence_id( cursor )
            logger.info(f"log id: {seq}")
            params = {
                "seq": seq,
                "onu_activity_name": str(onu_activity_name),
                "onu_command": str(onu_command),
                "user_name": str(user_name),
                "olt_ip": str(olt_ip),
                "onu_serial": str(onu_serial),
                "username": str(username),
                "password": str(password),
                "service_name": str(service_name),
                "stat_ip": str(stat_ip),
                "ip_address": str(ip_address),
                "mask_address": str(mask_address),
                "protocol_type": str(protocol_type),
                "onu_type": str(onu_type),
                "dns_one": str(dns_one),
                "dns_two": str(dns_two),
                "request": request,                 # bytes or None
                "onu_response": safe_raw(onu_response)     # bytes or None
                #"onu_activity_ts": onu_activity_ts
            }
            cursor.execute(sql, params)


            if auto_commit:
                conn.commit()

            logger.info(f"Inserted ONU activity log ID: {seq} | {onu_activity_name} | {onu_serial}")

            return int(seq)

    except oracledb.Error as e:
        logger.error(f"Failed to insert ONU activity log: {e}", exc_info=True)
        if 'conn' in locals() and conn:
            conn.rollback()
        raise

def get_command_with_template( command_name: str) -> dict:
    """
    Fetch command configuration with associated template details.
    
    Returns: dict with 'command' and 'template' keys, or None if not found
    """
    query = """
            SELECT
                CF.CONFIG_ID,
                CF.TEMPLATE_ID,
                CF.COMMANDS,
                CF.SUCCESS_RESPONSE,
                CF.ERROR_RESPONSE,
                CF.COMMAND_NAME,
                CF.COMMAND_PURPOSE,
                CF.ERROR_RESPONSE_PATTERN,
                CF.SUCCESS_RESPONSE_PATTERN,
                CF.DEVICE_NAME,
                CF.NESTED_TEMPLATE_ID ,
                CF.NESTED_FLAG,
                TP.TEMPLATE_ID,
                TP.LOGIN_TYPE,
                TP.USERNAME,
                TP.PASSWORD,
                TP.SECRET,
                TP.GLOBAL_DELAY_FACTOR,
                TP.PORT,
                TP.ENABLE_CUSTOM,
                TP.LINE_SEPERATOR,
                TP.HOST,
                TP.DEVICE_TYPE,
                TP.TEMPLATE_NAME,
                TP.TEMPLATE_EXPECT_STR,
                TP.TIMEOUT
            FROM
            {command_configuration} CF
            INNER JOIN {template_master} TP ON
                TP.TEMPLATE_ID = CF.TEMPLATE_ID
            WHERE
                CF.COMMAND_NAME =  :command_name
            ORDER BY CF.SEQUENCE
    """.format(command_configuration=command_configuration, template_master=template_master)
    logger.info(f"query: {query}")
    try:
        with get_oracle_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, command_name=command_name)
            row = cursor.fetchall()
        
            if not row:
                raise ValueError(f"No command/template found for '{command_name}'")
            
            result = {
                'commands': [
                    {
                        'config_id': r[0],
                        'template_id': r[1],
                        'commands': r[2],
                        'success_response': r[3],
                        'error_response': r[4],
                        'command_name': r[5],
                        'command_purpose': r[6],
                        'error_response_pattern': r[7],
                        'success_response_pattern': r[8],
                        'device_name': r[9],
                        'ns_flag':r[11],
                        'ns_template_id':r[10]
                    }
                    for r in row
                ],
                'template': {
                    'template_id': row[0][12],
                    'login_type': row[0][13],
                    'username': row[0][14],
                    'password': row[0][15],
                    'secret': row[0][16],
                    'global_delay_factor': row[0][17],
                    'port': row[0][18],
                    'enable_custom': row[0][19],
                    'line_separator': row[0][20],
                    'host': row[0][21],
                    'device_type': row[0][22],
                    'template_name': row[0][23],
                    'template_expect_str':row[0][24],
                    'timeout':row[0][25]
                }
            }
            logger.debug(f"Fetched command '{command_name}' with template")
            return result
        
    except Exception as e:
        logger.error(f"Failed to fetch command with template '{command_name}': {e}")
        raise

def get_nested_command_configuration_by_id( template_id: int ) -> dict:
    """
    Fetch nested command configuration by template_id.
    
    Returns: dict with nessted command configuration details
    """
    query = """
       SELECT TEMPLATE_ID,COMMANDS,ERROR_PATTERN,SUCCESS_PATTERN,SEQUENCE FROM {nested_configuration} WHERE TEMPLATE_ID=:template_id
    """.format(nested_configuration=nested_configuration)
    logger.debug(f"query: {query}")
    try:
        with get_oracle_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, template_id=template_id)
            row = cursor.fetchall()
        
        if not row:
            raise ValueError(f"No configuration found for TEMPLATE_ID = {template_id}")
        
        result = [ 
            {
            'TEMPLATE_ID': r[0],
            'COMMANDS': r[1],
            'ERROR_PATTERN': r[2],
            'SUCCESS_PATTERN': r[3],
            'SEQUENCE': r[4]
            } for r in row
        ]
        
        logger.debug(f"Fetched nested command configuration for TEMPLATE_ID = {template_id}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to fetch nested configuration for TEMPLATE_ID = {template_id}: {e}")
        raise


def get_command_configuration_by_id( config_id: int ) -> dict:
    """
    Fetch command configuration by CONFIG_ID.
    
    Returns: dict with command configuration details
    """
    query = """
    SELECT CONFIG_ID, TEMPLATE_ID, COMMANDS, SUCCESS_RESPONSE, ERROR_RESPONSE,
           COMMAND_NAME, COMMAND_PURPOSE, ERROR_RESPONSE_PATTERN, 
           SUCCESS_RESPONSE_PATTERN, DEVICE_NAME
    FROM {command_configuration}
    WHERE CONFIG_ID = :config_id
    """.format(command_configuration=command_configuration)
    
    try:
        with get_oracle_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, config_id=config_id)
            row = cursor.fetchone()
        
        if not row:
            raise ValueError(f"No configuration found for CONFIG_ID = {config_id}")
        
        result = {
            'config_id': row[0],
            'template_id': row[1],
            'commands': row[2],
            'success_response': row[3],
            'error_response': row[4],
            'command_name': row[5],
            'command_purpose': row[6],
            'error_response_pattern': row[7],
            'success_response_pattern': row[8],
            'device_name': row[9],
        }
        
        logger.debug(f"Fetched command configuration for CONFIG_ID = {config_id}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to fetch configuration for CONFIG_ID = {config_id}: {e}")
        raise
        
def get_template_by_id( template_id: int) -> dict:
    """
    Fetch template details by TEMPLATE_ID.
    
    Returns: dict with template configuration or None if not found
    """
    query = """
    SELECT TEMPLATE_ID, LOGIN_TYPE, USERNAME, PASSWORD, SECRET, 
           GLOBAL_DELAY_FACTOR, PORT, ENABLE_CUSTOM, LINE_SEPERATOR, 
           HOST, DEVICE_TYPE, TEMPLATE_NAME
    FROM {template_master} 
    WHERE TEMPLATE_ID = :template_id
    """.format(template_master=template_master)
    
    try:
        with get_oracle_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, template_id=template_id)
            row = cursor.fetchone()
        
        if not row:
            logger.warning(f"No template found for TEMPLATE_ID = {template_id}")
            return None
        
        result = {
            'template_id': row[0],
            'login_type': row[1],
            'username': row[2],
            'password': row[3],
            'secret': row[4],
            'global_delay_factor': row[5],
            'port': row[6],
            'enable_custom': row[7],
            'line_separator': row[8],
            'host': row[9],
            'device_type': row[10],
            'template_name': row[11],
        }
        
        logger.debug(f"Fetched template ID {template_id}: {result['template_name']}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to fetch template {template_id}: {e}")
        raise