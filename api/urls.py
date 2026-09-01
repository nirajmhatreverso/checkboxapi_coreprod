from django.urls import path
from .views import InfoAPIView, ExecuteCommandsAPIView, DbLogSaveAPIView, UpsertCommandConfigurationAPIView, UpsertTemplateAPIView, infoAPIDBLogView, GetTemplateByIdAPIView, GetCommandConfigurationAPIView, GetCommandWithTemplateAPIView, ExecuteCommandsWithTemplateAPIView, ExecuteGenericTelnetAPIView

urlpatterns = [
    path('info/', InfoAPIView.as_view(), name='api-info'),
    path('execute/', ExecuteCommandsAPIView.as_view(), name='execute-commands'),
    path('save/', DbLogSaveAPIView.as_view(), name='db-logs'),
    path('infoActivity/', infoAPIDBLogView.as_view(), name='api-info-db'),
    path('GetTemplateById/',GetTemplateByIdAPIView.as_view(), name='get-db-temp-mst'),
    path('GetCmdConf/',GetCommandConfigurationAPIView.as_view(), name='get-db-conf-mst'),
    path('GetCmdWithTemp/',GetCommandWithTemplateAPIView.as_view(), name='get-db-conf-temp'),
    path('UpsertTmp/',UpsertTemplateAPIView.as_view(), name='upsert-template'),
    path('UpsertCmdConf/',UpsertCommandConfigurationAPIView.as_view(), name='upsert-cmd-conf'),
    path('executeWithTemplate/',ExecuteCommandsWithTemplateAPIView.as_view(), name='execute-commands-with-template'),
    path('executeTlt/',ExecuteGenericTelnetAPIView.as_view(), name='execute-generic-telnet'),
]