# Importaciones
import customtkinter as ctk
from customtkinter import CTkImage
from PIL import Image, ImageTk
import time
import os
import sys
import threading
import datetime
import subprocess as sub
import spacy # evita errores con chatterbot (no tocar, sino explota todo)
import pyttsx3
import speech_recognition as sr
import pywhatkit
import wikipedia
from chatterbot import ChatBot
from chatterbot.trainers import ListTrainer
import ws as whapp      # Usar Whatsapp
import database           # Base de datos para el chatbot


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")
#Intento fallido de usar pyinstaller (no afecta al rendimiento)
def load_spacy_model():
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            model_path = os.path.join(base_path, "en_core_web_sm")
            return spacy.load(model_path)
        else:
            return spacy.load("en_core_web_sm")
    except Exception as e:
        print(f"Error cargando spaCy: {e}")
        raise
nlp = load_spacy_model()

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Voz y reconocimiento de voz
engine = pyttsx3.init()
voices = engine.getProperty('voices')
# Protección por si la lista de voces es más corta
def safe_set_voice(idx):
    if 0 <= idx < len(voices):
        engine.setProperty('voice', voices[idx].id)
    else:
        # si no existe la voz pedida, usa la primera disponible para que no hayan errores :)
        engine.setProperty('voice', voices[0].id)

safe_set_voice(0)
engine.setProperty('rate', 145)

listener = sr.Recognizer()
talk_lock = threading.Lock()

# Diccionarios y variables para las funciones
contacts = {}
sites = {}
programs = {}
listening_active = False

# Entrenar el chatbot una vez y usé un metodo para evitar el error de pyinstaller
model_path = os.path.join(os.path.dirname(__file__), "en_core_web_sm")
if os.path.exists(model_path):
    spacy.load(model_path)
chatbot = ChatBot("Pepe", database_uri=None)  
trainer = ListTrainer(chatbot)
try:
    qna = database.get_q_n_a()
    if qna:
        trainer.train(qna)
except Exception as e:
    print(f"Error al entrenar el chatbot al iniciar: {e}")

# función de voz
def talk(text):
    with talk_lock:
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"Error en talk: {e}")
def read_and_talk():
    text = text_info.get("1.0", "end")
    talk(text)
def change_voice(id):
    safe_set_voice(id)
    engine.setProperty('rate', 145)
    talk("Hola, soy Pepe")

def mexican_voice(): change_voice(0)
def spanish_voice(): change_voice(2)
def english_voice(): change_voice(1)

# mini registro
def log_action(message):
    try:
        text_info.insert("end", f" {message}\n")
        text_info.see("end")
    except Exception:
        print("LOG:", message)

# Escucha del micrófono
def listen(timeout=None, phrase_time_limit=6):
    try:
        with sr.Microphone() as source:
            listener.adjust_for_ambient_noise(source, duration=0.8)
            audio = listener.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        try:
            rec = listener.recognize_google(audio, language="es-ES")
            return rec.lower()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print("Error servicio reconocimiento:", e)
            return ""
    except Exception as e:
        print("Error usando micrófono:", e)
        return ""

# Cargar datos de archivos
def charge_data(name_dict, name_file):
    try:
        with open(name_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                parts = line.strip().split(",", 1)
                if len(parts) == 2:
                    key, val = parts
                    name_dict[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Error charge_data {name_file}: {e}")

charge_data(sites, "pages.txt")
charge_data(programs, "apps.txt")
charge_data(contacts, "contacts.txt")

# Funciones
def reproduce(rec):
    music = rec.replace('reproduce', '').strip()
    if not music:
        talk("¿Qué quieres que reproduzca?")
        return
    talk("Reproduciendo " + music)
    log_action(f"🎵 Reproduciendo: {music}")
    pywhatkit.playonyt(music)

def busca(rec):
    search = rec.replace('busca', '').strip()
    if not search:
        talk("¿Qué quieres que busque?")
        return
    wikipedia.set_lang("es")
    try:
        wiki = wikipedia.summary(search, 1)
    except Exception:
        wiki = "No encontré un resumen claro sobre eso."
    log_action(f"🔍 Búsqueda: {search}")
    log_action(f"🧠 Resumen: {wiki}")
    talk(wiki)

def clock(rec):
    num = rec.replace('alarma', '').strip()
    # validar formato HH:MM
    try:
        if len(num) <= 2:  # si usuario dice solo la hora "7" o "07"
            num = num.zfill(2) + ":00"
        if ':' not in num:
            num = num[:2] + ":" + num[2:4] if len(num) >= 4 else num
        datetime.datetime.strptime(num, '%H:%M')  # lanza excepción si inválida
    except Exception:
        talk("Formato de hora inválido. Di la hora en formato 24 horas, por ejemplo 07:30 o 19:45")
        return

    talk("Alarma activada a las " + num + " horas")
    log_action(f"⏰ Alarma activada a las {num} horas")

    def alarma_worker(target_time):
        while True:
            if datetime.datetime.now().strftime('%H:%M') == target_time:
                try:
                    pywhatkit.playonyt("levantense")
                except Exception:
                    print("No se pudo reproducir alarma via playonyt")
                log_action("Levantate, tu alarma está sonando!")
                talk("Suena la alarma")
                break
            time.sleep(5)

    t = threading.Thread(target=alarma_worker, args=(num,), daemon=True)
    t.start()

def abre(rec):
    task = rec.replace('abre', '').strip()
    if task in sites:
        try:
            sub.call(f'start {sites[task]}', shell=True)
            log_action(f"🌐 Abriendo página: {task}")
            talk(f'Abriendo {task}')
        except Exception as e:
            log_action(f"❗ Error abriendo sitio: {e}")
            talk("No pude abrir la página.")
    elif task in programs:
        try:
            log_action(f"🛠️ Abriendo programa: {task}")
            talk(f'Abriendo {task}')
            os.startfile(programs[task])
        except Exception as e:
            log_action(f"❗ Error abriendo programa: {e}")
            talk("No pude abrir el programa.")
    else:
        log_action(f"❗ No se encontró: {task}")
        talk("Lo siento, no encontré esa app o página.")

def write(f):
    global listening_active
    talk("¿Qué quieres que escriba?")
    log_action(f"📝 Tienes 10 segundos para escribir tu nota rápida")
    talk("Espera 10 segundos si quieres hacerlo de forma oral")
    time.sleep(10)
    texto = text_comand.get().strip()
    if texto != "":
        rec = texto
        text_comand.delete(0, "end")
        time.sleep(1)
    else:
        talk("Empieza a hablar por favor")
        rec = listen()
    if rec:
        f.write(rec + os.linesep)
        log_action(f"📝 Nota escrita: {rec}")
        talk("Listo, puedes revisarlo")
        try:
            sub.Popen("nota.txt", shell=True)
        except Exception:
            pass
    else:
        talk("No se escribió nada.")

def escribe(rec):
    try:
        mode = 'a' if os.path.exists("nota.txt") else 'w'
        with open("nota.txt", mode, encoding="utf-8") as f:
            write(f)
    except Exception as e:
        print("Error escribe:", e)
        talk("Ocurrió un problema al guardar la nota.")

def enviar_mensaje(rec):
    global listening_active
    contact = rec.replace('mensaje', '').strip()
    if contact in contacts:
        contact_number = contacts[contact]
        talk("¿Qué mensaje quieres enviarle?")
        time.sleep(3)
        texto = text_comand.get().strip()
        if texto != "":
            message = texto
            text_comand.delete(0, "end")
        else:
            talk("Háblame ahora")
            message = listen()
        if message:
            talk("Enviando mensaje...")
            try:
                whapp.send_message(contact_number, message)
                log_action(f"📩 Mensaje a {contact}: {message}")
            except Exception as e:
                log_action(f"❌ Error enviando mensaje: {e}")
                talk("No pude enviar el mensaje.")
        else:
            talk("No hay contenido para el mensaje.")
    else:
        talk("Parece que aún no has agregado a ese contacto, usa el botón de agregar!")
        log_action(f"❌ Contacto no encontrado: {contact}")

def buscame(rec):
    busqueda = rec.replace("búscame", "").strip()
    if not busqueda:
        talk("¿Qué quieres que busque?")
        return
    log_action(f"🌐 Búsqueda web: {busqueda}")
    pywhatkit.search(busqueda)

def conversar(rec=None):
    talk("Vamos a conversar...")
    log_action("🗨️ Inició una conversación con el asistente")
    while True:
        request = listen()
        if not request:
            talk("No te entendí, intenta otra vez")
            continue
        if "hasta luego" in request:
            talk("Hasta la próxima")
            log_action("👋 Usuario finalizó la conversación")
            break
        try:
            answer = chatbot.get_response(request)
            talk(str(answer))
            log_action(f"👤 {request}")
            log_action(f"🤖 {answer}")
        except Exception as e:
            log_action(f"❌ Error en respuesta chatbot: {e}")
            talk("Lo siento, hubo un error en mi respuesta.")

# Diccionario de comandos
key_words = {
    'reproduce': reproduce,
    'busca': busca,
    'alarma': clock,
    'abre': abre,
    'escribe': escribe,
    'mensaje': enviar_mensaje,
    'búscame': buscame,
    'hablemos': conversar
}

# Función principal
def run_pp():
    global listening_active
    while listening_active:
        try:
            texto = text_comand.get().strip()
            if texto != "":
                rec = texto.lower().strip()
                text_comand.delete(0, "end")
                # pausa para evitar un error MUY posible
                time.sleep(0.5)
                listening_active = False
            else:
                rec = listen()
        except Exception:
            talk("No te entendí, intenta de nuevo")
            continue

        if not rec:
            continue

        if 'termina' in rec:
            talk("Adiós!")
            try:
                text_info.delete("1.0", "end")
            except Exception:
                pass
            listening_active = False
            break

        if "lista web" in rec:
            if not sites:
                talk("Parece que no has agregado ningún sitio web")
                log_action("📋 Lista de sitios vacía")
            else:
                text_info.delete("1.0", "end")
                log_action("📋 Lista de sitios web:")
                log_action(str(sites))
                read_and_talk()
                try:
                    text_info.delete("1.0", "end")
                except Exception:
                    pass
            continue

        if "lista de programas" in rec:
            if not programs:
                talk("Parece que no has agregado ningun programa")
                log_action("📋 Lista de programas vacía")
            else:
                text_info.delete("1.0", "end")
                log_action("📋 Lista de programas:")
                log_action(str(programs))
                read_and_talk()
                try:
                    text_info.delete("1.0", "end")
                except Exception:
                    pass
            continue

        if "lista de contactos" in rec:
            if not contacts:
                talk("Parece que no has agregado ningun contacto")
                log_action("📋 Lista de contactos vacía")
            else:
                text_info.delete("1.0", "end")
                log_action("📋 Lista de contactos:")
                log_action(str(contacts))
                read_and_talk()
                try:
                    text_info.delete("1.0", "end")
                except Exception:
                    pass
            continue

        # ejecutar comando principal
        for word in key_words:
            if word in rec:
                try:
                    key_words[word](rec)
                except Exception as e:
                    log_action(f"❌ Error ejecutando comando '{word}': {e}")
                break
    # antes usaba main_window.update() pero me trajo problemas así que me desice de él

# Ventana principal que me demoró 1 mes en entender ☠
main_window = ctk.CTk()
main_window.iconbitmap("icono.ico")
main_window.title("Pepe AI")
main_window.geometry("1300x800")
main_window.minsize(900, 600)
main_window.configure(fg_color="#1E1E2F")
main_window.columnconfigure(0, weight=1)
main_window.rowconfigure(0, weight=1)

# Marco principal
main_frame = ctk.CTkFrame(main_window, fg_color="#1E1E2F")
main_frame.grid(row=0, column=0, sticky="nsew")
main_frame.columnconfigure(0, weight=3)
main_frame.columnconfigure(1, weight=1)
main_frame.rowconfigure(0, weight=1)

# Submarco izquierdo
left_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
left_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
left_frame.columnconfigure(0, weight=1)
left_frame.rowconfigure(1, weight=1)

label_title = ctk.CTkLabel(left_frame, text="Pepe AI",
                           font=('Arial', 30, 'bold'), text_color="white")
label_title.grid(row=0, column=0, pady=(0, 10))

text_comand = ctk.CTkEntry(left_frame, placeholder_text="Escribe aquí tu comando")
text_comand.grid(row=2, column=0, pady=10, sticky="ew")

def enviar_a_chatbot():
    request = text_comand.get().strip()
    if request == "":
        return
    text_comand.delete(0, "end")

    if "hasta luego" in request.lower():
        talk("Hasta la próxima")
        log_action("👋 Usuario finalizó la conversación")
        return

    try:
        answer = chatbot.get_response(request)
        log_action(f"👤 {request}")
        log_action(f"🤖 {answer}")
        talk(str(answer))
    except Exception as e:
        log_action(f"❌ Error al obtener respuesta del chatbot: {e}")
        talk("Lo siento, no pude responder ahora.")

ctk.CTkButton(left_frame, text="Enviar mensaje 💬", command=enviar_a_chatbot,
              fg_color="#1ABC9C", hover_color="#148F77",
              text_color="white", font=("Arial", 13, "bold"),
              height=40, corner_radius=20).grid(row=3, column=0, pady=5, sticky="ew")

text_comand.bind("<Return>", lambda event: enviar_a_chatbot())

text_info = ctk.CTkTextbox(left_frame,
                           fg_color="#2C2C3E",
                           text_color="white",
                           font=("Consolas", 12),
                           wrap="word")
text_info.grid(row=1, column=0, sticky="nsew")

# Submarco derecho
right_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
right_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
right_frame.columnconfigure(0, weight=1)

# Voces del sistema (solo en mi caso. Tambien es reescribible para añadir otros idiomas con relativa facilidad así que no es muy inconveniente)
voice_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
voice_frame.grid(row=1, column=0, pady=(5, 10), sticky="ew")

ctk.CTkLabel(voice_frame, text="Voces disponibles", text_color="white",
             font=("Arial", 14, "bold")).pack(pady=(0, 5))

ctk.CTkButton(voice_frame, text="Voz México", command=mexican_voice,
              fg_color="green", hover_color="#117A34",
              text_color="white", font=("Arial", 14, "bold"),
              height=45, corner_radius=20).pack(pady=2, fill="x")

ctk.CTkButton(voice_frame, text="Voz Hispana", command=spanish_voice,
              fg_color="red", hover_color="#B03A2E",
              text_color="white", font=("Arial", 14, "bold"),
              height=45, corner_radius=20).pack(pady=2, fill="x")

ctk.CTkButton(voice_frame, text="Voz USA", command=english_voice,
              fg_color="blue", hover_color="#1F618D",
              text_color="white", font=("Arial", 14, "bold"),
              height=45, corner_radius=20).pack(pady=2, fill="x")

def talk_text_box_input():
    texto = text_comand.get().strip()
    if texto:
        talk(texto)

ctk.CTkButton(voice_frame, text="Hablar 🗣", command=talk_text_box_input,
              fg_color="#2e4053", hover_color="#2ecc71",
              text_color="white", font=("Arial", 14, "bold"),
              height=45, corner_radius=20).pack(pady=2, fill="x")

# Agregar windows para páginas/contactos/apps
def open_w_pages():
    global namepage_entry, pathf_entry

    window_pages = ctk.CTkToplevel()
    window_pages.title("Agregar página web")
    window_pages.geometry("500x300")
    window_pages.iconbitmap("icono.ico")
    window_pages.configure(fg_color="#2C2C3E")
    window_pages.resizable(False, False)

    # Título
    ctk.CTkLabel(window_pages, text="Agrega una página web", text_color="white",
                 font=('Arial', 18, 'bold')).pack(pady=10)

    # Nombre de la página
    ctk.CTkLabel(window_pages, text="Nombre de la página", text_color="white").pack(pady=(10, 0))
    namepage_entry = ctk.CTkEntry(window_pages, placeholder_text="Ej. YouTube")
    namepage_entry.pack(pady=5)

    # Ruta (URL)
    ctk.CTkLabel(window_pages, text="Ruta de la página", text_color="white").pack(pady=(10, 0))
    pathf_entry = ctk.CTkEntry(window_pages, placeholder_text="https://www.youtube.com")
    pathf_entry.pack(pady=5)

    # Botón guardar
    ctk.CTkButton(window_pages, text="Guardar", command=add_pages,
                  fg_color="#2980B9", hover_color="#21618C", corner_radius=15,
                  font=("Arial", 13, "bold")).pack(pady=20)


def open_w_contacts():
    global namecontacts_entry, phone_entry

    window_contacts = ctk.CTkToplevel()
    window_contacts.title("Agregar contacto")
    window_contacts.iconbitmap("icono.ico")
    window_contacts.geometry("500x300")
    window_contacts.configure(fg_color="#2C2C3E")
    window_contacts.resizable(False, False)

    # Título
    ctk.CTkLabel(window_contacts, text="Agrega un contacto", text_color="white",
                 font=('Arial', 18, 'bold')).pack(pady=10)

    # Nombre del contacto
    ctk.CTkLabel(window_contacts, text="Nombre del contacto", text_color="white").pack(pady=(10, 0))
    namecontacts_entry = ctk.CTkEntry(window_contacts, placeholder_text="Ej. Mamá")
    namecontacts_entry.pack(pady=5)

    # Número del contacto
    ctk.CTkLabel(window_contacts, text="Número de teléfono", text_color="white").pack(pady=(10, 0))
    phone_entry = ctk.CTkEntry(window_contacts, placeholder_text="Ej. +51987654321")
    phone_entry.pack(pady=5)

    # Botón guardar
    ctk.CTkButton(window_contacts, text="Guardar", command=add_contacts,
                  fg_color="#27AE60", hover_color="#1e8449", corner_radius=15,
                  font=("Arial", 13, "bold")).pack(pady=20)
    
def open_w_apps():
    global nameapp_entry, path_entry

    window_apps = ctk.CTkToplevel()
    window_apps.title("Agregar aplicación")
    window_apps.iconbitmap("icono.ico")
    window_apps.geometry("500x300")
    window_apps.configure(fg_color="#2C2C3E")
    window_apps.resizable(False, False)

    # Título
    ctk.CTkLabel(window_apps, text="Agrega una aplicación", text_color="white",
                 font=('Arial', 18, 'bold')).pack(pady=10)

    # Nombre del programa
    ctk.CTkLabel(window_apps, text="Nombre del programa", text_color="white").pack(pady=(10, 0))
    nameapp_entry = ctk.CTkEntry(window_apps, placeholder_text="Ej. Calculadora")
    nameapp_entry.pack(pady=5)

    # Ruta de la app
    ctk.CTkLabel(window_apps, text="Ruta del programa", text_color="white").pack(pady=(10, 0))
    path_entry = ctk.CTkEntry(window_apps, placeholder_text="C:/Ruta/Calculadora.exe")
    path_entry.pack(pady=5)

    # Botón guardar
    ctk.CTkButton(window_apps, text="Guardar", command=add_apps,
                  fg_color="#9B59B6", hover_color="#7D3C98", corner_radius=15,
                  font=("Arial", 13, "bold")).pack(pady=20)

# Cree un sistema de guardado con archivos de nota al ser mis unicas "Bases de datos" que logro comprender
def add_apps():
    name = nameapp_entry.get().strip()
    path = path_entry.get().strip()
    programs[name] = path
    save_data(name, path, "apps.txt")
    nameapp_entry.delete(0, "end")
    path_entry.delete(0, "end")

def add_contacts():
    name_contacts = namecontacts_entry.get().strip()
    phone = phone_entry.get().strip()
    contacts[name_contacts] = phone
    save_data(name_contacts, phone, "contacts.txt")
    namecontacts_entry.delete(0, "end")
    phone_entry.delete(0, "end")

def add_pages():
    name = namepage_entry.get().strip()
    path = pathf_entry.get().strip()
    sites[name] = path
    save_data(name, path, "pages.txt")
    namepage_entry.delete(0, "end")
    pathf_entry.delete(0, "end")

def save_data(key, value, file_name):
    try:
        with open(file_name, 'a', encoding="utf-8") as f:
            f.write(key + "," + value + "\n")
    except Exception as e:
        print("Error save_data:", e)

# Ayuda (literalmente una ventana de ayuda)
def open_help_window():
    help_window = ctk.CTkToplevel()
    help_window.title("Ayuda de comandos")
    help_window.iconbitmap("icono.ico")
    help_window.geometry("600x500")
    help_window.iconbitmap("icono.ico")
    help_window.configure(fg_color="#2C2C3E")
    help_window.resizable(False, False)
    ctk.CTkLabel(help_window, text="🛈 Comandos de voz disponibles",
                 text_color="white", font=('Arial', 20, 'bold')).pack(pady=15)
    help_text = """
===========Funciones del asistente===========
1.Reproduce _____(Nombre de música o video)
2.Escribe (Para hacer una nota rapida por voz o texto si es requerido)
3.Hablemos (Inicia el chatbot integrado)
4.Abre _____(Sitio web/ Archivo/ ejecutable)
5.Alarma ____(Hora en formato 24:00)
6.Busca _____(Tema de búsqueda para una obtener info rápida por wikipedia)
7.Búscame ____(Tema de búsqueda para buscar por la web)
8.Lista ____ (Lista web/de contactos/de programas para obtener tus datos guardados)
9.Mensaje ____(nombre del contacto)
10.Termina (Termina el ciclo de escucha, en resumen Pepe deja de escucharte
Dato: Para una mejor capatación de lo que dices, puedes hablar lento y antes de decir el comando decir "Pepe..." de esta forma se podrá procesar mejor lo que dices.
"""
    text_box = ctk.CTkTextbox(help_window, font=("Arial", 14),
                              fg_color="#1E1E2F", text_color="white",
                              wrap="word", corner_radius=10)
    text_box.insert("1.0", help_text)
    text_box.configure(state="disabled")
    text_box.pack(padx=20, pady=10, fill="both", expand=True)
    ctk.CTkButton(help_window, text="Cerrar", command=help_window.destroy,
                  fg_color="#E74C3C", hover_color="#C0392B", text_color="white",
                  corner_radius=15, font=("Arial", 14, "bold")).pack(pady=10)

# Botón escuchar
def toggle_listen():
    global listening_active
    if not listening_active:
        listening_active = True
        threading.Thread(target=run_pp, daemon=True).start()
        talk("Empiezo a escuchar")
    else:
        listening_active = False
        talk("Escucha detenida")

main_controls_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
main_controls_frame.grid(row=3, column=0, pady=(5, 10), sticky="ew")

ctk.CTkButton(main_controls_frame, text="🎙 Escuchar", command=toggle_listen,
              fg_color="#1565C0", hover_color="#0D47A1",
              text_color="white", font=("Arial", 18, "bold"),
              height=45, corner_radius=25).pack(fill="x")

# Imagen del asistente (con protección para que se adapte a cambios de pantalla y resolución)
def resize_image_to_frame(image_path, frame, scale=0.8):
    try:
        frame.update_idletasks()
        width = max(100, int(frame.winfo_width() * scale))
        height = max(100, int(frame.winfo_height() * scale))
        pil_image = Image.open(resource_path(image_path)).resize((width, height))
        return CTkImage(pil_image, size=(width, height))
    except Exception as e:
        print("No se pudo cargar imagen:", e)
        return None
# Marcos para botones
options_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
options_frame.grid(row=2, column=0, pady=(5, 10), sticky="ew")

ctk.CTkLabel(options_frame, text="Agregar elementos", text_color="white",
             font=("Arial", 14, "bold")).pack(pady=(0, 5))

ctk.CTkButton(options_frame, text="📇 Agregar Contactos", command=open_w_contacts,
              fg_color="#4286f4", hover_color="#2b65d9",
              text_color="white", font=("Arial", 14, "bold"),
              height=45, corner_radius=20).pack(pady=3, fill="x")

ctk.CTkButton(options_frame, text="🌐 Agregar Páginas", command=open_w_pages,
              fg_color="#34ace0", hover_color="#2276aa",
              text_color="white", font=("Arial", 14, "bold"),
              height=45, corner_radius=20).pack(pady=3, fill="x")

ctk.CTkButton(options_frame, text="🖥️ Agregar Apps", command=open_w_apps,
              fg_color="#9b59b6", hover_color="#7e3d9a",
              text_color="white", font=("Arial", 14, "bold"),
              height=45, corner_radius=20).pack(pady=3, fill="x")

ctk.CTkButton(options_frame, text="🛈 Ayuda", command=open_help_window,
              fg_color="#8E44AD", hover_color="#6C3483",
              text_color="white", font=("Arial", 14, "bold"),
              height=45, corner_radius=20).pack(pady=3, fill="x")

pp_image = resize_image_to_frame("PP.jpg", right_frame)
if pp_image:
    window_photo = ctk.CTkLabel(right_frame, image=pp_image, text="")
    window_photo.grid(row=0, column=0, pady=(10, 10), sticky="n")

# Ejecutar interfaz
main_window.mainloop()
