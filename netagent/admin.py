from django.contrib import admin
from django.db import OperationalError, DatabaseError
# Register your models here.

from .models import PyaTmpMaster, PyaCommandConfiguration, PyaNestedConfiguration, UatOnuTemplateConfiguration

class OracleSafeAdminMixin:
    """Prevents the admin list page from crashing if Oracle is unreachable."""
    def changelist_view(self, request, extra_context=None):
        try:
            return super().changelist_view(request, extra_context)
        except (OperationalError, DatabaseError) as e:
            from django.contrib import messages
            messages.error(request, f"Oracle connection error: {e}")
            from django.shortcuts import redirect
            return redirect('/admin/')

@admin.register(PyaTmpMaster)
class PyaTmpMasterAdmin(admin.ModelAdmin):
    list_display = ('template_id', 'template_name', 'login_type', 'username', 'password','enable_custom','line_seperator','device_type','template_timeout')
    search_fields = ('template_name', 'login_type', 'device_type')
    list_filter = ('login_type', 'device_type')


@admin.register(PyaCommandConfiguration)
class PyaCommandConfigurationAdmin(admin.ModelAdmin):
    list_display = ('config_id', 'command_name','commands', 'template', 'device_name','success_response_pattern' ,'error_response_pattern' ,'success_resp','error_resp','sequence')
    search_fields = ('command_name', 'template', 'device_name')
    list_filter = ('device_name','command_name')
    raw_id_fields = ('template',)


@admin.register(PyaNestedConfiguration)
class PyaNestedConfigurationAdmin(admin.ModelAdmin):
    list_display = ('template_id','error_pattern','success_pattern','commands' ,'sequence')
    search_fields = ('commands','error_pattern','template_id','success_pattern',)



@admin.register(UatOnuTemplateConfiguration)
class UatOnuTemplateConfigurationAdmin(admin.ModelAdmin):
    list_display = ('command_name', 'upstream_profile', 'connection_type', 'vendor', 'model', 'type', 'action', 'status')
    search_fields = ('command_name', 'vendor', 'model')
    list_filter = ('vendor', 'model', 'status')