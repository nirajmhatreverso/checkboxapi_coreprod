from django.db import models
from django.db import connection
from django.conf import settings

template_master = settings.DATABASES['table']['template_master']
nested_configuration = settings.DATABASES['table']['nested_configuration']
command_configuration = settings.DATABASES['table']['command_configuration']
template_configuration = settings.DATABASES['table']['template_configuration']

class PyaTmpMaster(models.Model):
    """
    Maps to PYA_TMP_MASTER
    PK auto-incremented by Oracle trigger PK_TMP_ID + sequence PYA_TMP_MASTER_SEQ.
    """
    template_id = models.AutoField(
        primary_key=True,
        db_column='TEMPLATE_ID',
    )
    login_type = models.CharField(max_length=20, null=True, blank=True, db_column='LOGIN_TYPE')
    username = models.CharField(max_length=30, null=True, blank=True, db_column='USERNAME')
    password = models.CharField(max_length=40, null=True, blank=True, db_column='PASSWORD')
    secret = models.CharField(max_length=50, null=True, blank=True, db_column='SECRET')
    global_delay_factor = models.CharField(max_length=20, null=True, blank=True, db_column='GLOBAL_DELAY_FACTOR')
    port = models.CharField(max_length=20, null=True, blank=True, db_column='PORT')
    enable_custom = models.CharField(max_length=20, null=True, blank=True, db_column='ENABLE_CUSTOM')
    line_seperator = models.CharField(max_length=20, null=True, blank=True, db_column='LINE_SEPERATOR')
    host = models.CharField(max_length=20, null=True, blank=True, db_column='HOST')
    device_type = models.CharField(max_length=20, null=True, blank=True, db_column='DEVICE_TYPE')
    template_name = models.CharField(max_length=100, null=True, blank=True, db_column='TEMPLATE_NAME')
    template_expect_str = models.CharField(max_length=200, null=True, blank=True, db_column='TEMPLATE_EXPECT_STR')
    template_timeout = models.CharField(max_length=20, null=True, blank=True, db_column='TIMEOUT')

    class Meta:
        app_label = 'netagent'
        # managed=False means Django will NOT create/alter/drop this table
        # Remove managed=False and run makemigrations to let Django manage it
        managed = False
        db_table = 'PYA_TMP_MASTER'

    def __str__(self):
        return f"{self.template_name} (id={self.template_id})"


class PyaCommandConfiguration(models.Model):
    """
    Maps to PYA_COMMAND_CONFIGURATION
    PK auto-incremented by Oracle trigger PK_CONFIG_ID + sequence PYA_COMMAND_CONFIG_SEQ.
    """
    config_id = models.AutoField(primary_key=True, db_column='CONFIG_ID')
    template = models.ForeignKey(
        PyaTmpMaster,
        on_delete=models.PROTECT,
        db_column='TEMPLATE_ID',
        null=True, blank=True,
        related_name='commands',
    )
    commands = models.CharField(max_length=500, null=True, blank=True, db_column='COMMANDS')
    success_response = models.CharField(max_length=200, null=True, blank=True, db_column='SUCCESS_RESPONSE')
    error_response = models.CharField(max_length=200, null=True, blank=True, db_column='ERROR_RESPONSE')
    command_name = models.CharField(max_length=30, null=True, blank=True, db_column='COMMAND_NAME')
    command_purpose = models.CharField(max_length=1000, null=True, blank=True, db_column='COMMAND_PURPOSE')
    error_response_pattern = models.CharField(max_length=200, null=True, blank=True, db_column='ERROR_RESPONSE_PATTERN')
    success_response_pattern = models.CharField(max_length=200, null=True, blank=True, db_column='SUCCESS_RESPONSE_PATTERN')
    device_name = models.CharField(max_length=20, null=True, blank=True, db_column='DEVICE_NAME')
    nested_flag = models.DecimalField(max_digits=10, decimal_places=0, default=0, null=True, blank=True, db_column='NESTED_FLAG')
    nested_template_id = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, db_column='NESTED_TEMPLATE_ID')
    sequence = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, db_column='SEQUENCE')
    config_name = models.CharField(max_length=50, null=True, blank=True, db_column='CONFIG_NAME')
    description = models.CharField(max_length=128, null=True, blank=True, db_column='DESCRIPTION')
    created_date = models.CharField(max_length=50, null=True, blank=True, db_column='CREATED_DATE')
    modified_date = models.CharField(max_length=50, null=True, blank=True, db_column='MODIFIED_DATE')
    created_by = models.CharField(max_length=50, null=True, blank=True, db_column='CREATED_BY')
    modified_by = models.CharField(max_length=50, null=True, blank=True, db_column='MODIFIED_BY')
    success_resp = models.CharField(max_length=50, null=True, blank=True, db_column='SUCCESS_RESP')
    error_resp = models.CharField(max_length=50, null=True, blank=True, db_column='ERROR_RESP')
    column12 = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, db_column='COLUMN12')

    class Meta:
        app_label = 'netagent'
        managed = False
        db_table = 'PYA_COMMAND_CONFIGURATION'

    def __str__(self):
        return f"{self.command_name} (config_id={self.config_id})"


class PyaNestedConfiguration(models.Model):
    """
    Maps to PYA_NESTEST_CONFIGURATION
    No trigger-based PK in Oracle DDL; TEMPLATE_ID used as primary key.
    """
    template_id = models.IntegerField(primary_key=True, db_column='TEMPLATE_ID')
    commands = models.CharField(max_length=500, null=True, blank=True, db_column='COMMANDS')
    error_pattern = models.CharField(max_length=500, null=True, blank=True, db_column='ERROR_PATTERN')
    success_pattern = models.CharField(max_length=500, null=True, blank=True, db_column='SUCCESS_PATTERN')
    sequence = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, db_column='SEQUENCE')

    class Meta:
        app_label = 'netagent'
        managed = False
        db_table = 'PYA_NESTEST_CONFIGURATION'

    def __str__(self):
        return f"NestedConfig template_id={self.template_id}"


class UatOnuTemplateConfiguration(models.Model):
    id = models.IntegerField(db_column='ID', primary_key=True)
    command_name = models.CharField(db_column='COMMAND_NAME', max_length=250, blank=True, null=True)  # Field name made lowercase.
    upstream_profile = models.CharField(db_column='UPSTREAM_PROFILE', max_length=100, blank=True, null=True)  # Field name made lowercase.
    connection_type = models.CharField(db_column='CONNECTION_TYPE', max_length=100, blank=True, null=True)  # Field name made lowercase.
    vendor = models.CharField(db_column='VENDOR', max_length=100, blank=True, null=True)  # Field name made lowercase.
    model = models.CharField(db_column='MODEL', max_length=100, blank=True, null=True)  # Field name made lowercase.
    type = models.CharField(db_column='TYPE', max_length=100, blank=True, null=True)  # Field name made lowercase.
    action = models.CharField(db_column='ACTION', max_length=100, blank=True, null=True)  # Field name made lowercase.
    status = models.CharField(db_column='STATUS', max_length=100, blank=True, null=True, default='A')  # Field name made lowercase.
 
    class Meta:
        app_label = 'netagent'
        managed = False
        db_table = 'uat_onu_template_configuration'