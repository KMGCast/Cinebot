
from django.contrib import admin
from django.urls import path
from bot.views import pagina_chat, api_chat, exportar_chat, borrar_historial

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', pagina_chat),
    path('api/chat/', api_chat),
    path('descargar/', exportar_chat),
    path('borrar/', borrar_historial),
    
]
