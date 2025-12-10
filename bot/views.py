from django.shortcuts import render, redirect 
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient
import json
import socket
from ollama import Client 

# Config inicial de mongo
try:
    client = MongoClient('mongodb://db:27017', serverSelectionTimeoutMS=2000)
    client.server_info()
except:
    client = MongoClient('mongodb://localhost:27017')

db = client['cine_db']
historial_chats = db['historial_chats'] 

# Configuración adicional de ollama para que espere a gemma3 (mi compu viejita no es tan potente así que tarda en procesar :c)
def obtener_cliente_ollama():
    try:
        socket.gethostbyname('ollama')
#Agregar tiempo extra de espera
        return Client(host='http://ollama:11434', timeout=300)
    except:
        return Client(host='http://localhost:11434', timeout=300)

cliente_ollama = obtener_cliente_ollama()

#Funciones
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
        data = json.loads(request.body)
        mensaje_usuario = data.get('mensaje', '')
        modo = data.get('modo', 'recomendacion')

 #Promts: 
        if modo == 'busqueda':
            sistema = "Eres un experto buscando películas y series de TV. Adivina el título."
        elif modo == 'series':
            sistema = "Eres un experto en series de TV. Recomienda con plataforma."
        elif modo == 'trivia':
            sistema = "Eres experto en curiosidades de cine."
        else:
            sistema = "Eres un crítico de cine. Recomienda con año, director y un resumen de la trama."

#Memoria
        historial_reciente = list(historial_chats.find({'modo': modo}).sort('_id', -1).limit(5))
        historial_reciente.reverse()

#Crear "Mensajes"
        mensajes_para_enviar = [{"role": "system", "content": sistema}]

        for charla in historial_reciente:
            mensajes_para_enviar.append({"role": "user", "content": charla['usuario']})
            mensajes_para_enviar.append({"role": "assistant", "content": charla['bot']})

        mensajes_para_enviar.append({"role": "user", "content": mensaje_usuario})

        try:
#Llamando al modelo (gemma3 en este caso)
            response = cliente_ollama.chat(
                model='gemma3',  
                messages=mensajes_para_enviar,
                stream=False,
                options={
                    "temperature": 0.2,
                    "num_predict": 500 
                }
            )

            texto_bot = response['message']['content']
            
#Generar historial
            historial_chats.insert_one({
                "usuario": mensaje_usuario,
                "bot": texto_bot,
                "modo": modo
            })

            return JsonResponse({'respuesta': texto_bot})
            
        except Exception as e:
#Monitoreo de errores en la terminal
            print(f"ERROR: {e}") 
            return JsonResponse({'respuesta': f"Error: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Método no permitido'}, status=405)

#Exportar historial en un archivo .txt
def exportar_chat(request):
    conversaciones = historial_chats.find()
    
    texto_archivo = "---Historial de conversación con CineBot---\n\n"

    for conversacion in conversaciones:
        usuario = conversacion.get('usuario', '')
        bot = conversacion.get('bot', ' ')
        modo = conversacion.get('modo', 'general')

        texto_archivo += f"[Modo: {modo}]\n"
        texto_archivo += f"Tú: {usuario}\n"
        texto_archivo += f"CineBot: {bot}\n"
        texto_archivo += "-" * 30 + "\n"

    response = HttpResponse(texto_archivo, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="Historial_cinebot.txt"'
    return response