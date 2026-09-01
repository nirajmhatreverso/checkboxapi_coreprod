from rest_framework import serializers
from .models import PyaTmpMaster, PyaCommandConfiguration, PyaNestedConfiguration


class PyaTmpMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = PyaTmpMaster
        fields = [
            'template_id', 'login_type', 'username', 'password', 'secret',
            'global_delay_factor', 'port', 'enable_custom', 'line_seperator',
            'host', 'device_type', 'template_name', 'template_expect_str',
        ]
        # Mark password/secret as write_only for security in responses
        extra_kwargs = {
            'password': {'write_only': False},  # set True in production
            'secret':   {'write_only': False},
        }


class PyaCommandConfigurationSerializer(serializers.ModelSerializer):
    # Expose template_id as a plain integer (writeable), not the nested object
    template_id = serializers.PrimaryKeyRelatedField(
        source='template',
        queryset=PyaTmpMaster.objects.using('oracle').all(),
    )

    class Meta:
        model = PyaCommandConfiguration
        fields = [
            'config_id', 'template_id', 'commands', 'success_response',
            'error_response', 'command_name', 'command_purpose',
            'error_response_pattern', 'success_response_pattern', 'device_name',
            'nested_flag', 'nested_template_id', 'sequence', 'config_name',
            'description', 'created_date', 'modified_date',
            'created_by', 'modified_by', 'success_resp', 'error_resp', 'column12',
        ]


class PyaCommandConfigurationReadSerializer(serializers.ModelSerializer):
    """Flat read serializer — used when returning joined command+template data."""
    template = PyaTmpMasterSerializer(read_only=True)

    class Meta:
        model = PyaCommandConfiguration
        fields = [
            'config_id', 'template', 'commands', 'success_response',
            'error_response', 'command_name', 'command_purpose',
            'error_response_pattern', 'success_response_pattern', 'device_name',
        ]


class PyaNestedConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PyaNestedConfiguration
        fields = [
            'template_id', 'commands', 'error_pattern', 'success_pattern', 'sequence',
        ]

class PyaCommandConfSerializer(serializers.ModelSerializer):
    template_id = serializers.IntegerField(source='template.template_id')
    ns_flag = serializers.IntegerField(source='nested_flag')
    ns_template_id = serializers.IntegerField(source='nested_template_id')
 
    class Meta:
        model = PyaCommandConfiguration
        fields = [
            "config_id",
            "template_id",
            "commands",
            "success_response",
            "error_response",
            "command_name",
            "command_purpose",
            "error_response_pattern",
            "success_response_pattern",
            "device_name",
            "ns_flag",
            "ns_template_id",
        ]
 
class PyaTempMasterSerializer1(serializers.ModelSerializer):
    line_separator = serializers.CharField(source='line_seperator')
 
    class Meta:
        model = PyaTmpMaster
        fields = [
            "template_id",
            "template_name",
            "device_type",
            "login_type",
            "username",
            "password",
            "secret",
            "global_delay_factor",
            "port",
            "enable_custom",
            "line_separator",
            "host",
            "template_expect_str",
            "timeout",
        ]
 
class TemplateWithCommandsSerializer(serializers.Serializer):
    commands = PyaCommandConfSerializer(many=True)
    template = PyaTempMasterSerializer1()
