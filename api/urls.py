from django.urls import path
from .views import InfoAPIView, ExecuteCommandsAPIView, DbLogSaveAPIView, infoAPIDBLogView

urlpatterns = [
    path('info/', InfoAPIView.as_view(), name='api-info'),
    path('execute/', ExecuteCommandsAPIView.as_view(), name='execute-commands'),
    path('save/', DbLogSaveAPIView.as_view(), name='db-logs'),
    path('infoActivity/', infoAPIDBLogView.as_view(), name='api-info-db'),
]