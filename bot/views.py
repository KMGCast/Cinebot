from django.shortcuts import render, redirect 
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient
import json
import socket
from ollama import Client 
import time
import os


#Configuración para identificar contenedor: Localhost o AWS
if os.path.exists('/.dockerenv'):
    print(" Entorno detectado: DOCKER (Local o AWS)")
    HOST_DB = 'db'
    HOST_OLLAMA = 'ollama'
else:
    print("Entorno detectado: WINDOWS (Localhost)")
    HOST_DB = 'localhost'
    HOST_OLLAMA = 'localhost'


print("Iniciando conexión a la Base de Datos")

# Conexion a Mongo
client = None
while True:
    try:
        # Usamos la variable HOST_DB que definimos arriba
        client = MongoClient(f'mongodb://{HOST_DB}:27017', serverSelectionTimeoutMS=3000)
        
        # Tocamos la puerta
        client.server_info()

        print(f"onectado a MongoDB en host: '{HOST_DB}'")
        break # Rompemos el bucle si conectó
    except Exception as e:
        # Si falla, esperamos 3 segundos y volvemos a intentar
        print(f"La base de datos aún no responde ({e}). Reintentando en 3 seg")
        time.sleep(3)

# Config inicial de base de datos conectada

db = client['cine_db']
historial_chats = db['historial_chats'] 

# Configuración adicional de ollama para que espere a gemma3 (mi compu viejita no es tan potente así que tarda en procesar :c)
def obtener_cliente_ollama():
    
    ruta= f'http://{HOST_OLLAMA}:11434'
    print(f"ConfigUrando Ollama en: {ruta}")
    #Se extendió el tiempo de respuesta porque mi PC está chikita y no puele :c
    return Client(host=ruta, timeout=500)

cliente_ollama = obtener_cliente_ollama()

#Funciones vista y lógica de CineBot

#1: Cragar pág
def pagina_chat(request):
    return render(request, 'chat.html')
#2:Borrar historial del chat + Recargar la pag limpia
def borrar_historial(request):
    historial_chats.delete_many({})
    return redirect('/')
#3:Chatbot
@csrf_exempt
def api_chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            mensaje_usuario = data.get('mensaje', '')
            modo = data.get('modo', 'recomendacion')
            user_id = data.get('user_id', 'Anónimo')

            # Prompts: 
            if modo == 'busqueda':
                sistema = "Eres un experto buscando películas y series de TV de acuerdo a la trama que te describen. Adivina el título."
            elif modo == 'series':
                sistema = "Eres un experto en series de TV. Recomienda con plataforma."
            elif modo == 'trivia':
                sistema = "Eres experto en curiosidades de cine."
            else:
                sistema = "Eres un crítico de cine. Recomienda con año, director y un breve resumen de la trama."

            # Memoria (limitado a 10 mensajes)
            historial_reciente = list(historial_chats.find({'modo': modo}).sort('_id', -1).limit(10))
            historial_reciente.reverse()

            # Crear "Mensajes"
            mensajes_para_enviar = [{"role": "system", "content": sistema}]

            for charla in historial_reciente:
                mensajes_para_enviar.append({"role": "user", "content": charla['usuario']})
                mensajes_para_enviar.append({"role": "assistant", "content": charla['bot']})

            mensajes_para_enviar.append({"role": "user", "content": mensaje_usuario})

            # Llamando al modelo
            inicio = time.time() 
            response = cliente_ollama.chat(
                model='gemma3',  
                messages=mensajes_para_enviar,
                stream=False,
                options={
                    "temperature": 0.5,
                    "top_p": 0.8,
                    "num_predict": 400
                }
            )
            fin = time.time()
            tiempo_total = round(fin - inicio, 2)

            texto_bot = response['message']['content']
            
            # Guardar historial
            historial_chats.insert_one({
                "user_id": user_id,
                "usuario": mensaje_usuario,
                "bot": texto_bot,
                "modo": modo,
                "tiempo_respuesta": tiempo_total
            })
            
            print(f"[IA] Respondió a {user_id} en {tiempo_total}s", flush=True)

            return JsonResponse({'respuesta': texto_bot})
            
        except Exception as e:
            # Monitoreo de errores
            print(f"❌ ERROR: {e}") 
            return JsonResponse({'respuesta': f"Error: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Método no permitido'}, status=405)

#Exportar historial en un archivo .txt
def exportar_chat(request):
    conversaciones = historial_chats.find()
    
    texto_archivo = "---Historial de conversación con CineBot---\n\n"

    for conversacion in conversaciones:
        u_id = conversacion.get ('user_id', 'Desconocido')
        usuario = conversacion.get('usuario', '')
        bot = conversacion.get('bot', ' ')
        modo = conversacion.get('modo', 'general')


        texto_archivo += f"[{u_id}] - [Modo: {modo}]\n"
        texto_archivo += f"Tú: {usuario}\n"
        texto_archivo += f"CineBot: {bot}\n"
        texto_archivo += "-" * 30 + "\n"

    response = HttpResponse(texto_archivo, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="Historial_cinebot.txt"'
    return response
