# utils/db.py
import oracledb
from django.conf import settings
from contextlib import contextmanager
import logging
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo


from .logging_config import setup_logging

#logger = logging.getLogger(__name__)
logger = setup_logging(debug=False)

#logger = setup_logging(debug=False) 
# Option A: Use credentials directly (less secure, but simple)
# CONNECTION_PARAMS = {
#     "user": "reports",
#     "password": "2322",
#     "dsn": "172.20.20.24:1213/misdb"
# }

# Option B: Better – store in Django settings (recommended)
# settings.py:
# ORACLE_DB = {
#     'USER': 'reports',
#     'PASSWORD': '2322',
#     'HOST': '172.20.20.24',
#     'PORT': 1213,
#     'SERVICE_NAME': 'misdb'
# }

@contextmanager
def get_oracle_connection():
    """Context manager for safe Oracle connection handling"""
    conn = None
    try:
        # Modern way - using service name (preferred)
        oracledb.init_oracle_client()
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

# Example usage in views.py / services / anywhere
def some_business_function():
    with get_oracle_connection() as conn:
        cursor = conn.cursor()
        
        # SELECT example
        cursor.execute("""
            SELECT id, name, amount 
            FROM transactions 
            WHERE status = 'PENDING' 
            AND created_at > SYSDATE - 7
        """)
        rows = cursor.fetchall()
        
        # INSERT example
        cursor.execute("""
            INSERT INTO processed_logs (transaction_id, processed_at, status)
            VALUES (:1, SYSDATE, 'SUCCESS')
        """, [12345])
        
        conn.commit()           # very important!
      

def get_sequence_id(cursor, seq_name: str = "ONU_ACTIVITY_LOG_DETAILS_SEQ") -> int:
    """Standalone way to get next sequence value as int"""
    cursor.execute(f"SELECT {seq_name}.NEXTVAL FROM DUAL")
    return int(cursor.fetchone()[0])  # always returns NUMBER → safe to int()
    
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
    Insert a record into REPORTS.ONU_ACTIVITY_LOG_DETAILS
    Returns the generated ONU_ACTIVITY_LOG_ID (from sequence)
    """
    
    sql = """
    INSERT INTO REPORTS.ONU_ACTIVITY_LOG_DETAILS (
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
    """
#    
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
                "onu_response": onu_response     # bytes or None
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