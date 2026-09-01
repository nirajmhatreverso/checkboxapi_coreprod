"""
core/db_router.py

Routes all netagent models to the 'oracle' database.
Everything else (auth, sessions, admin) continues to use 'default' (SQLite).
"""

ORACLE_APPS = {'netagent'}


class OracleRouter:
    """
    A router that sends all netagent model operations to the 'oracle' database.
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label in ORACLE_APPS:
            return 'oracle'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in ORACLE_APPS:
            return 'oracle'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations within the oracle app set
        if (
            obj1._meta.app_label in ORACLE_APPS
            and obj2._meta.app_label in ORACLE_APPS
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        netagent models have managed=False, so Django won't actually run DDL.
        This just prevents Django from attempting oracle migrations on 'default'.
        """
        if app_label in ORACLE_APPS:
            return db == 'oracle'
        return db == 'default'