import sys
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class NetagentConfig(AppConfig):
    name = 'netagent'

    def ready(self):
        """
        Called once by Django when the app registry is fully loaded.
        This is the correct place to init python-oracledb thick mode —
        it runs before any DB connection is made, and runs exactly once.
        """
        try:
            import oracledb

            if sys.platform == "win32":
                # Point to your Instant Client folder on Windows
                oracledb.init_oracle_client(
                    lib_dir=r"C:\instantclient-basic-windows\instantclient_23_0"
                )
            else:
                # Linux/Mac: Instant Client must be on LD_LIBRARY_PATH,
                # or pass lib_dir="/opt/oracle/instantclient_21_6" explicitly
                oracledb.init_oracle_client()

            logger.info("python-oracledb thick mode initialised successfully")

        except Exception as e:
            # Log but don't crash startup — connections will fail with a clear error
            logger.warning(f"python-oracledb thick mode init failed: {e}")