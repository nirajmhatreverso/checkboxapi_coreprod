"""
api/views_orm.py

Drop-in replacement for the raw-SQL calls in views.py.
All DB access goes through Django ORM + the 'oracle' database router.

Usage in views.py — replace:
    from .utils.db import get_command_with_template, get_template_by_id, ...
With:
    from .views_orm import (
        orm_get_command_with_template,
        orm_get_template_by_id,
        orm_get_command_configuration_by_id,
        orm_upsert_template_mst,
        orm_upsert_command_configuration,
        orm_upsert_nested_configuration,
    )
"""

import logging
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from netagent.models import (
    PyaTmpMaster,
    PyaCommandConfiguration,
    PyaNestedConfiguration,
)
from netagent.serializers import (
    PyaTmpMasterSerializer,
    PyaCommandConfigurationSerializer,
    PyaCommandConfigurationReadSerializer,
    PyaNestedConfigurationSerializer,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# All ORM queries route to the 'oracle' database alias defined in settings.py
# ---------------------------------------------------------------------------
DB = 'oracle'


def _template_to_dict(obj: PyaTmpMaster) -> dict:
    return {
        'template_id': obj.template_id,
        'login_type': obj.login_type,
        'username': obj.username,
        'password': obj.password,
        'secret': obj.secret,
        'global_delay_factor': obj.global_delay_factor,
        'port': obj.port,
        'enable_custom': obj.enable_custom,
        'line_separator': obj.line_seperator,   # note: db column typo preserved
        'host': obj.host,
        'device_type': obj.device_type,
        'template_name': obj.template_name,
        'template_expect_str': obj.template_expect_str,
    }


def _command_to_dict(obj: PyaCommandConfiguration) -> dict:
    return {
        'config_id': obj.config_id,
        'template_id': obj.template_id,
        'commands': obj.commands,
        'success_response': obj.success_response,
        'error_response': obj.error_response,
        'command_name': obj.command_name,
        'command_purpose': obj.command_purpose,
        'error_response_pattern': obj.error_response_pattern,
        'success_response_pattern': obj.success_response_pattern,
        'device_name': obj.device_name,
    }


# ---------------------------------------------------------------------------
# READ helpers
# ---------------------------------------------------------------------------

def orm_get_template_by_id(template_id: int) -> dict:
    """Replaces: get_template_by_id(template_id)"""
    try:
        obj = PyaTmpMaster.objects.using(DB).get(template_id=template_id)
        logger.debug(f"Fetched template id={template_id}")
        return _template_to_dict(obj)
    except ObjectDoesNotExist:
        logger.warning(f"No template found for TEMPLATE_ID={template_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch template {template_id}: {e}")
        raise


def orm_get_command_configuration_by_id(config_id: int) -> dict:
    """Replaces: get_command_configuration_by_id(config_id)"""
    try:
        obj = PyaCommandConfiguration.objects.using(DB).get(config_id=config_id)
        logger.debug(f"Fetched command config id={config_id}")
        return _command_to_dict(obj)
    except ObjectDoesNotExist:
        raise ValueError(f"No configuration found for CONFIG_ID={config_id}")
    except Exception as e:
        logger.error(f"Failed to fetch configuration {config_id}: {e}")
        raise


def orm_get_command_with_template(command_name: str) -> dict:
    """
    Replaces: get_command_with_template(command_name)

    Returns:
        {
            'commands': [ {...}, ... ],
            'template': { ... }
        }
    """
    try:
        qs = (
            PyaCommandConfiguration.objects
            .using(DB)
            .select_related('template')
            .filter(command_name=command_name)
        )
        if not qs.exists():
            raise ValueError(f"No command/template found for '{command_name}'")

        commands_list = [_command_to_dict(row) for row in qs]
        # All rows share the same template (JOIN result); take first row's template
        template_obj = qs[0].template
        template_dict = _template_to_dict(template_obj) if template_obj else {}

        logger.debug(f"Fetched {len(commands_list)} command(s) for '{command_name}'")
        return {
            'commands': commands_list,
            'template': template_dict,
        }
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch command with template '{command_name}': {e}")
        raise


def orm_get_nested_configuration(template_id: int) -> dict:
    """Replaces: get_command_configuration_by_id(template_id) [nested variant]"""
    try:
        obj = PyaNestedConfiguration.objects.using(DB).get(template_id=template_id)
        return {
            'TEMPLATE_ID': obj.template_id,
            'COMMANDS': obj.commands,
            'ERROR_PATTERN': obj.error_pattern,
            'SUCCESS_PATTERN': obj.success_pattern,
            'SEQUENCE': obj.sequence,
        }
    except ObjectDoesNotExist:
        raise ValueError(f"No nested configuration found for TEMPLATE_ID={template_id}")
    except Exception as e:
        logger.error(f"Failed to fetch nested config {template_id}: {e}")
        raise


# ---------------------------------------------------------------------------
# WRITE helpers  (update_or_create replaces MERGE INTO … DUAL)
# ---------------------------------------------------------------------------

@transaction.atomic(using=DB)
def orm_upsert_template_mst(
    template_name: str,
    login_type: str,
    username: str,
    password: str,
    secret: str = None,
    global_delay_factor=None,
    port=None,
    enable_custom: str = None,
    line_seperator: str = None,
    host: str = None,
    device_type: str = None,
) -> int:
    """
    Replaces: upsert_template_mst(...)
    Returns TEMPLATE_ID (int).
    """
    defaults = {
        'login_type': login_type,
        'username': username,
        'password': password,
        'secret': secret,
        'global_delay_factor': str(global_delay_factor) if global_delay_factor is not None else None,
        'port': str(port) if port is not None else None,
        'enable_custom': enable_custom,
        'line_seperator': line_seperator,
        'host': host,
        'device_type': device_type,
    }
    obj, created = PyaTmpMaster.objects.using(DB).update_or_create(
        template_name=template_name,
        defaults=defaults,
    )
    action = "Inserted" if created else "Updated"
    logger.info(f"{action} template '{template_name}' TEMPLATE_ID={obj.template_id}")
    return obj.template_id


@transaction.atomic(using=DB)
def orm_upsert_command_configuration(
    command_name: str,
    template_id: int,
    commands: str,
    success_response: str = None,
    error_response: str = None,
    command_purpose: str = None,
    error_resp_pattern: str = None,
    success_resp_pattern: str = None,
    device_name: str = None,
) -> int:
    """
    Replaces: upsert_command_configuration(...)
    Returns CONFIG_ID (int).
    """
    # Resolve the FK object
    try:
        template_obj = PyaTmpMaster.objects.using(DB).get(template_id=template_id)
    except ObjectDoesNotExist:
        raise ValueError(f"Template with TEMPLATE_ID={template_id} not found")

    defaults = {
        'template': template_obj,
        'commands': commands,
        'success_response': success_response,
        'error_response': error_response,
        'command_purpose': command_purpose,
        'error_response_pattern': error_resp_pattern,
        'success_response_pattern': success_resp_pattern,
        'device_name': device_name,
    }
    obj, created = PyaCommandConfiguration.objects.using(DB).update_or_create(
        command_name=command_name,
        defaults=defaults,
    )
    action = "Inserted" if created else "Updated"
    logger.info(f"{action} command '{command_name}' CONFIG_ID={obj.config_id}")
    return obj.config_id


@transaction.atomic(using=DB)
def orm_upsert_nested_configuration(
    template_id: int,
    commands: str,
    error_pattern: str = None,
    success_pattern: str = None,
    sequence: int = None,
) -> int:
    """
    Replaces: upsert_nested_command_configurations(...)
    Returns TEMPLATE_ID (int).
    """
    defaults = {
        'commands': commands,
        'error_pattern': error_pattern,
        'success_pattern': success_pattern,
        'sequence': sequence,
    }
    obj, created = PyaNestedConfiguration.objects.using(DB).update_or_create(
        template_id=template_id,
        defaults=defaults,
    )
    action = "Inserted" if created else "Updated"
    logger.info(f"{action} nested config TEMPLATE_ID={template_id}")
    return obj.template_id