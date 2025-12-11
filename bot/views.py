from django.shortcuts import render, redirect 
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo import MongoClient
import json
import socket
from ollama import Client 
import time

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
        user_id= data.get('user_id', 'Anónimo')

 #Promts: 
        if modo == 'busqueda':
            sistema = "Eres un experto buscando películas y series de TV de acuerdo a la trama que te describen. Adivina el título."
        elif modo == 'series':
            sistema = "Eres un experto en series de TV. Recomienda con plataforma."
        elif modo == 'trivia':
            sistema = "Eres experto en curiosidades de cine."
        else:
            sistema = "Eres un crítico de cine. Recomienda con año, director y un breve resumen de la trama."

#Memoria por ahora limitado a 10 mensajes
        historial_reciente = list(historial_chats.find({'modo': modo}).sort('_id', -1).limit(10))
        historial_reciente.reverse()

#Crear "Mensajes"
        mensajes_para_enviar = [{"role": "system", "content": sistema}]

        for charla in historial_reciente:
            mensajes_para_enviar.append({"role": "user", "content": charla['usuario']})
            mensajes_para_enviar.append({"role": "assistant", "content": charla['bot']})

        mensajes_para_enviar.append({"role": "user", "content": mensaje_usuario})

        try:
#Llamando al modelo (gemma3 en este caso)
            inicio = time.time() 
            response = cliente_ollama.chat(
                model='gemma3',  
                messages=mensajes_para_enviar,
                stream=False,
                options={
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "num_predict": 400
                }
            )
            fin= time.time()
            tiempo_total=round(fin - inicio, 2)

            texto_bot = response['message']['content']
            
#Generar historial
            historial_chats.insert_one({
                "user_id": user_id,
                "usuario": mensaje_usuario,
                "bot": texto_bot,
                "modo": modo,
                "tiempo_respuesta": tiempo_total
            })
            print (f"[Gemma2] Respodió a {user_id} en {tiempo_total}s", flush=True)

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
