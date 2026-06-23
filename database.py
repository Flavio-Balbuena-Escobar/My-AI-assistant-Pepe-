import sqlite3

def create_connection():
    connection = sqlite3.connect("brain.db")
    return connection
def get_table():
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("select * from respuestas")
    return cursor.fetchall()

chat_list = list()
def get_q_n_a():
    chat_list = []
    rows = get_table()
    for pregunta, respuesta in rows:
        chat_list.append(pregunta)
        chat_list.append(respuesta)
    return chat_list


