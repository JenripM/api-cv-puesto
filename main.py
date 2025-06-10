from fpdf import FPDF
from io import BytesIO
import requests
import tempfile  
import matplotlib.pyplot as plt
import numpy as np
import re
from fastapi import FastAPI, UploadFile, File
import openai
from pdf_reader import extract_text_from_pdf
import os
from dotenv import load_dotenv
from fastapi.responses import StreamingResponse
import altair as alt
import pandas as pd
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import json
import shutil
import hashlib
import zipfile
import io
import json
import re
import requests
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import green, red, yellow, black, HexColor, white
import math
from math import pi, cos, sin
import numpy as np
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from math import cos, sin, pi
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.units import mm
import time


pdfmetrics.registerFont(TTFont('Poppins-Regular', './fonts/Poppins-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Poppins-Bold', './fonts/Poppins-Bold.ttf'))
pdfmetrics.registerFont(TTFont('Poppins-SemiBold', './fonts/Poppins-SemiBold.ttf'))
pdfmetrics.registerFont(TTFont('Poppins-Italic', './fonts/Poppins-Italic.ttf'))

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

from urllib.parse import urlparse

def obtener_nombre_archivo_desde_url(url: str) -> str:
    """
    Extrae el nombre del archivo desde una URL.
    Ej: https://myworkinpe.lat/pdfs/cv_1744315148575_4af9adfd.pdf → cv_1744315148575_4af9adfd.pdf
    """
    parsed_url = urlparse(url)
    return parsed_url.path.split("/")[-1]

def clean_and_load_json(response_str):
    # Elimina bloques de markdown como ```json ... ```
    cleaned = re.sub(r"```(?:json)?\n?", "", response_str.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"```$", "", cleaned.strip())
    return json.loads(cleaned)

# FUNCIONES PARA COMPLEMENTAR JSON DASHBOARD

def generate_analysis_id(candidate_name):
    # Extrae iniciales del nombre
    initials = ''.join([word[0] for word in candidate_name.split() if word]).upper()

    # Fecha y hora actual
    now = datetime.now().strftime('%Y%m%d%H%M%S')

    # Hash corto basado en nombre y timestamp
    hash_short = hashlib.md5((candidate_name + now).encode()).hexdigest()[:6]

    # ID único
    return f"{initials}-{now}-{hash_short}"

def generate_user_id(candidate_name):
    normalized_name = candidate_name.lower().replace(" ", "")
    hash_short = hashlib.md5(normalized_name.encode()).hexdigest()[:8]
    return f"user_{hash_short}"

def extract_email(text):
    # Expresión regular para identificar un correo electrónico
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    # Buscar el correo electrónico en el texto
    email_match = re.search(email_pattern, text)
    
    if email_match:
        return email_match.group(0)  # Devuelve el primer email encontrado
    else:
        return None  # Si no se encuentra ningún correo
    
def extract_phone(text):
    # Expresión regular para buscar un número de teléfono (ejemplo: (555) 555-5555 o 555-555-5555)
    phone_pattern = r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'
    phone_match = re.search(phone_pattern, text)
    if phone_match:
        return phone_match.group(0)  # Devuelve el primer teléfono encontrado
    else:
        return "No disponible"

def extract_linkedin(text):
    # Expresión regular para buscar un enlace de LinkedIn (por ejemplo: https://www.linkedin.com/in/usuario/)
    linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/in/[\w-]+'
    linkedin_match = re.search(linkedin_pattern, text)
    if linkedin_match:
        return linkedin_match.group(0)  # Devuelve el primer enlace de LinkedIn encontrado
    else:
        return "No disponible"

def extract_address(text):
    # Expresión regular para buscar una dirección (básica, puede necesitar ajustes dependiendo del formato)
    address_pattern = r'(?:Calle|Av\.|Avenida|Pje\.)\s?[a-zA-Z0-9\s,.-]+'
    address_match = re.search(address_pattern, text)
    if address_match:
        return address_match.group(0)  # Devuelve la primera dirección encontrada
    else:
        return "No disponible"


@app.get("/analizar-cv/")
async def analizar_cv(pdf_url: str, puesto_postular: str):
    start_time = time.time()
    end_time = time.time()
    processing_time_ms = int((end_time - start_time) * 1000)  # Convertir a milisegundos
    analysis_datetime = datetime.now().isoformat()  # "YYYY-MM-DDTHH:MM:SS"
    
    original_pdf = pdf_url

    response = requests.get(pdf_url)

    
    puesto = puesto_postular

    if response.status_code != 200:
        return {"error": "No se pudo descargar el archivo PDF."}
    
    pdf_content = BytesIO(response.content)

    contenido, num_paginas = extract_text_from_pdf(pdf_content)

    email = extract_email(contenido)


    #  return JSONResponse(contenido)
    prompt0 = f"""
    Actúa como un analista experto en CVs. Tu tarea es **extraer el nombre completo del candidato** que aparece en el siguiente contenido textual de un currículum. El nombre suele estar ubicado al inicio o en una sección de datos personales o encabezado.

    - Si identificas un nombre completo, devuélvelo.
    - Si solo aparece un nombre parcial, extrae lo más completo posible.
    - Si no encuentras un nombre claro, responde con "No identificado".

    Devuelve exclusivamente un objeto JSON con esta estructura:

    {{
    "nombre": "Nombre completo extraído o 'No identificado'"
    }}

    Contenido del CV:
    \"\"\"{contenido}\"\"\"
    """

    response0 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt0}],
        temperature=0.7,
       # max_tokens=100
    )
    candidate_name = response0['choices'][0]['message']['content']


    prompt1 = f"""
    Eres un reclutador profesional. Recibirás el perfil de un candidato en formato JSON y deberás evaluar su idoneidad para el puesto de "{puesto}".

    Evalúa cuidadosamente estos aspectos:
    - Experiencia laboral relevante para el puesto.
    - Habilidades técnicas y blandas necesarias.
    - Formación académica y complementaria alineada al rol.
    - Actitudes y aptitudes generales que favorezcan un buen desempeño en el puesto.

    Con base en tu análisis, responde exclusivamente con un **objeto JSON** con la siguiente estructura:

    {{
        "porcentaje": número entre 0 y 100, indicando qué tan alineado está el perfil con el puesto,
        "estado": una leyenda basada en el porcentaje, siguiendo esta escala:
            - 75 o más: "Aprobado"
            - Entre 50 y 74: "Con potencial"
            - Menor a 50: "No aprobado",
        "analisis": un único párrafo breve, que comience con "Tu CV", y que exprese una sola idea clara sobre el punto más relevante del perfil (ya sea una fortaleza o una oportunidad de mejora)
    }}

    Ejemplo de salida válida:

    {{
        "porcentaje": 78,
        "estado": "Aprobado",
        "analisis": "Tu CV demuestra actitud, base técnica y experiencias que suman. Pero hoy describe tareas, no comunica
        impacto. Con ajustes en redacción, métricas, lenguaje sectorial y presentación, puedes convertir un perfil
        prometedor en uno competitivo."
    }}

    No incluyas ningún otro texto fuera del JSON.

    A continuación, el perfil del candidato:

    {contenido}
    """

    response1 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt1}],
        temperature=0.7,
       # max_tokens=100
    )
    mainly_analysis = response1['choices'][0]['message']['content']


    prompt2 = f"""
    Eres un reclutador senior con amplia experiencia en la evaluación de currículums para procesos de selección competitivos.

    Tu tarea es analizar únicamente el número de páginas de un CV y emitir una evaluación profesional, comenzando siempre con una frase clara de diagnóstico general.

    Primero debes comenzar el comentario con una de estas frases (elige según el caso):
    - "¡Tu CV tiene el tamaño ideal!"
    - "Tu CV es demasiado extenso y puede jugar en contra."
    - "Tu CV tiene buen contenido, pero se puede optimizar en longitud."

    Luego, continúa con una observación más desarrollada y fundamentada, teniendo en cuenta:
    - Si facilita o no una lectura ágil por parte del reclutador.
    - Si permite resaltar la información clave.
    - Si sigue buenas prácticas de presentación ejecutiva (especialmente para perfiles no académicos).

    Responde con un único objeto JSON que contenga:

    Ejemplo de respuesta:

    {{
        "paginas"`: el número total de páginas del CV (ya proporcionado).
        "comentario"`: la evaluación clara y profesional, iniciando con una de las frases mencionadas y luego desarrollando una recomendación breve pero experta, maximo 37 palabras.

    }}

    No incluyas ningún texto fuera del JSON.

    Número de páginas del CV: {num_paginas}
    """


    response2 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt2}],
        temperature=0.7,
       # max_tokens=100
    )
    pagination = response2['choices'][0]['message']['content']



    
    prompt3 = f"""
    Actúa como un corrector profesional de ortografía con experiencia en revisión de currículums (CVs).

    Analiza el siguiente texto y detecta únicamente errores ortográficos reales.

    Debes ignorar lo siguiente:
    - Enlaces o URLs (por ejemplo: https://..., http://...).
    - Correos electrónicos y nombres de usuario.
    - Nombres propios de personas, empresas, instituciones, países, etc.
    - Siglas y abreviaciones en mayúsculas (como UX, TI, HTML).
    - Uso de mayúsculas al inicio de oración (no lo consideres error).

    Detecta únicamente errores como:
    - Palabras mal escritas o con letras cambiadas.
    - Tildes mal colocadas o faltantes.
    - Errores ortográficos frecuentes (como "desarollo" en lugar de "desarrollo").

    Tu respuesta debe ser exclusivamente un JSON con la siguiente estructura:

    {{
        "errores": número total de errores encontrados (entero),
        "comentario": comentario correspondiente según cantidad de errores, redactado en primera persona (por ejemplo: "Encontré 3 errores que te sugiero corregir para que el CV se vea más profesional."),
        "detalle_errores": si hay errores, una lista con objetos en el formato:
            [
            {{
                "original": "palabra con error",
                "sugerencia": "palabra corregida"
            }}
            ],
            si no hay errores, debe ser null
    }}

    Solo incluye en "detalle_errores" palabras donde "original" y "sugerencia" sean diferentes.

    No agregues texto fuera del JSON.

    Texto a analizar:
    \"\"\"{contenido}\"\"\"
    """


    response3 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt3}],
        temperature=0.7,
        #max_tokens=50  
    )
    
    spelling = response3['choices'][0]['message']['content']

    filename = obtener_nombre_archivo_desde_url(pdf_url)
   
    filename_json = json.dumps(filename)
    contenido_json = json.dumps(contenido)

    prompt4 = f"""
    Eres un experto en marca personal y empleabilidad. Tu tarea es analizar el nombre del archivo de un currículum (CV) para determinar si es profesional.

    Evalúa únicamente el **nombre del archivo PDF**: {filename_json}

    Considera si:
    - Es fácil de identificar por el reclutador.
    - Contiene el nombre del candidato o al menos algo representativo.
    - Evita combinaciones de números aleatorios o palabras genéricas.
    - Transmite orden y seriedad profesional.

    Considera este contenido del CV: {contenido_json}

    Responde SOLO en JSON con esta estructura:

    {{
    "archivo": {filename_json},
    "comentario": "Habla en primera persona. Dime si el nombre del archivo es adecuado o no, explícame por qué con lenguaje directo y profesional (por ejemplo: 'Tu archivo actual no es fácil de identificar porque...'). Si aplica, sugiere un nombre más claro y profesional (por ejemplo: 'Te sugiero cambiarlo por algo como Nombre_Apellido_CV.pdf')."
    }}
    """




    response4 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt4}],
        temperature=0.7,
        #max_tokens=50
    )
    filename_response = response4['choices'][0]['message']['content']

    print("filename_response", filename_response)

    prompt5 = f"""
    Actúa como un reclutador profesional experto en evaluación de currículums.

    Analiza si los siguientes elementos clave están presentes, bien ubicados y son fácilmente identificables en el CV:

    - Nombre
    - Correo electrónico
    - Experiencia laboral
    - Formación académica

    Responde exclusivamente en formato JSON con la siguiente estructura (no incluyas ningún texto fuera del JSON):

    {{
    "indispensable": {{
        "evaluacion": [
        {{
            "elemento": "Nombre",
            "existe": boolean,
            "bien_posicionado": boolean,
            "facil_de_distinguir": boolean
        }},
        {{
            "elemento": "Correo electrónico",
            "existe": boolean,
            "bien_posicionado": boolean,
            "facil_de_distinguir": boolean
        }},
        {{
            "elemento": "Experiencia laboral",
            "existe": boolean,
            "bien_posicionado": boolean,
            "facil_de_distinguir": boolean
        }},
        {{
            "elemento": "Formación académica",
            "existe": boolean,
            "bien_posicionado": boolean,
            "facil_de_distinguir": boolean
        }}
        ],
        "comentario_general": "Comentario personalizado en primera persona, con un maximo 40 palabras. Usa frases como 'yo veo', 'te recomiendo', 'me parece', 'considero' y evita construcciones impersonales como 'se observa'."
    }}
    }}

    Texto del CV:
    \"\"\"{contenido}\"\"\"
    """


    response5 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt5}],
        temperature=0.7,
        #max_tokens=50  
    )

    indispensable = response5['choices'][0]['message']['content']

    prompt6 = f"""
    Actúa como un revisor profesional de CVs. Tu tarea es detectar únicamente **palabras que se repiten de forma innecesaria o excesiva** en el siguiente texto.

     **Ignora las siguientes categorías de palabras**:
    - Artículos: el, la, los, las, un, una, unos, unas
    - Preposiciones: de, en, con, por, para, sobre, entre, hasta, hacia, desde
    - Conjunciones y conectores: y, o, u, pero, aunque, sino, mientras, así, entonces
    - Pronombres comunes: yo, tú, él, ella, nosotros, ustedes, ellos
    - Verbos muy comunes: ser, estar, haber, tener, hacer (solo si no están en exceso)
    - Monosílabos vacíos de contenido: a, e, es, al, lo, sí, no, se, que, qué, ya, más
    - Palabras similares con diferencia de género o número (ej: "capacidad" y "capacidades" se cuentan como una sola)
    - No me repitas la misma palabra como palabras diferentes, acumula 1 vez mas en el contador de veces.
    - SOLO PALABRAS REPETIDAS DONDE VECES SEA COMO MINIMO 2
    - SOLAMENTE DAME UN MAXIMO DE 12 PALABRAS

    Devuelve **solo** un JSON con esta estructura:

    {{ 
    "palabras_repetidas": [
        {{ "palabra": "x", "veces": n }},
    ]
    }}

    No incluyas ningún texto fuera del JSON.

    Texto a revisar:
    \"\"\"{contenido}\"\"\"
    """


    response6 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt6}],
        temperature=0.7,
        #max_tokens=50  
    )

    repeat_words = response6['choices'][0]['message']['content']

    prompt7 = f"""
    Imagina que eres un revisor de currículums con experiencia en selección de personal. Tu tarea es revisar el CV de una persona que postula al siguiente cargo: **{puesto_postular}**.

    Tu objetivo es dar una **opinión profesional y cercana** sobre si la experiencia laboral de la persona está **vigente** y si **realmente aporta valor para el puesto al que postula**.

    Habla de tú a tú, como si dieras una recomendación directa al candidato. Usa un **solo párrafo, maximo 70 palabras**, en tono natural (sin parecer una IA ni usar lenguaje técnico innecesario) No saludes, que se vea natural. No quiero mensajes de aliento, no necesito mensajes de exclamacion. se un profesional.


    Evalúa:
    - Si la experiencia es reciente (últimos 10-15 años).
    - Si está alineada al cargo o al tipo de trabajo que se espera.
    - Si hay continuidad profesional o vacíos laborales importantes.
    - No comentes sobre estudios, habilidades o redacción.

    Ejemplos del tono esperado:
    - "Veo que tu experiencia reciente en atención al cliente encaja bien con lo que se busca en este puesto, aunque te recomiendo resaltar más logros concretos."
    - "Has trabajado hace tiempo en roles similares, pero sería ideal actualizar tu experiencia con algo más reciente para estar al día con lo que el mercado pide."
    - "Tuviste un rol interesante en logística hace unos años, pero hay un vacío importante desde entonces; te recomiendo explicar eso para evitar dudas."

    Texto del CV:
    \"\"\"{contenido}\"\"\"
    """


    response7 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt7}],
        temperature=0.7,
        #max_tokens=50  
    )
    relevance = response7['choices'][0]['message']['content']

    prompt8 = f"""
    Actúa como un reclutador profesional. Evalúa el uso de verbos de impacto en el siguiente currículum.

    Analiza:
    - Si el candidato usa verbos fuertes que transmiten logros, liderazgo o resultados (por ejemplo: lideré, optimicé, implementé).
    - Si los verbos son genéricos o poco potentes (como: ayudé, colaboré, realicé).
    - Si hay variedad o repetición.

    Devuelve un JSON con la siguiente estructura:

    {{
        "nivel": un número entero del 1 al 10, donde 10 representa un uso excelente de verbos de impacto.
        "comentario": El tono de las sugerencias deben ser exhortativas, como si estuvieras dando consejos prácticos al candidato. verbos activos y orientados a resultados. En primera persona. una observación profesional breve y clara, de aproximadamente 160 caracteres (no más de 180). Usa un estilo formal, sin emojis.
        "sugerencias": una lista de 3 sugerencias específicas para mejorar los verbos en la redacción del CV. Cada sugerencia debe tener un maximo de 25 palabras y explicar claramente cómo mejorar un verbo genérico o repetido, incluyendo un ejemplo concreto de reemplazo. El tono de las sugerencias deben ser exhortativas, como si estuvieras dando consejos prácticos al candidato. verbos activos y orientados a resultados.
    }}

    No incluyas ningún texto fuera del JSON.

    Texto del CV:
    \"\"\"{contenido}\"\"\"
    """


    response8 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt8}],
        temperature=0.7,
        #max_tokens=50  
    )
    verbos_impact = response8['choices'][0]['message']['content']


    prompt9 = f"""
    Actúa como un experto en redacción de currículums. Analiza únicamente el primer párrafo del perfil profesional que aparece a continuación.

    Ignora encabezados como “Perfil Profesional”, así como correos, teléfonos, links u otros datos de contacto. No incluyas esa información en el resultado.

    Tu objetivo es evaluar la redacción del texto actual y sugerir una versión mejorada que sea más clara, profesional y alineada con estándares actuales. Usa como guía el siguiente enfoque de redacción (no lo copies literalmente):

    Debe empezar con: "Estudiante de “Número” ciclo de “Carrera” en la/el “Nombre de la Universidad”". Sino tiene la informacion. Indica a Estudiante de 'X' de la carrera 'Y' de la Universidad 'Z' como recomendacion. A partir de ahí, describe la identidad profesional de forma integral, combinando elementos personales como mentalidad, valores o trayectoria con intereses profesionales, fortalezas, experiencias relevantes o áreas de especialización. El objetivo es proyectar una imagen clara, auténtica y alineada con las metas profesionales del estudiante. Añade un toque personal que haga sentir al lector que conoce al candidato, pero manteniendo un tono profesional y directo. de acuerdo al puesto de {puesto}.

    Recuerda 'X' seria reemplazado por el nombre de la carrera, y 'Y' por el nombre de la Universidad
    Devuelve solo un JSON con esta estructura:

    {{
    "actual": "Texto actual del primer párrafo, sin encabezados ni contactos.",
    "recomendado": "Texto recomendado, redactado de forma más clara y profesional, alineado con el enfoque sugerido."
    }}

    Texto del perfil:
    \"\"\"{contenido}\"\"\"
    """

    response9 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt9}],
        temperature=0.7,
        #max_tokens=50  
    )
    perfil_profesional = response9['choices'][0]['message']['content']


    prompt10 = f"""
    Actúa como un reclutador experto en selección de personal para el rol de {puesto}. Evalúa el contenido del siguiente CV y clasifícalo en las siguientes categorías:

    - Habilidades de análisis
    - Resultados cuantificables
    - Habilidades blandas
    - Lenguaje técnico

    Para cada categoría proporciona:
    1. Un nivel: Bajo, Medio o Alto.
    2. Una acción concreta para mejorar. El tono de la accion  deben ser exhortativas, como si estuvieras dando consejos prácticos al candidato. No uses verbos en infinitivo que termine en ar er ir, dime ordenes, hablame de tu a tu. Si es posible, sugiere reemplazos específicos en el formato: “cambia #X# por #Y#”, Maximo 30 palabras.

    Devuelve exclusivamente un objeto JSON con el siguiente formato:

    {{
        "habilidades_de_analisis": {{
            "nivel": "",
            "accion": ""
        }},
        "resultados_cuantificables": {{
            "nivel": "",
            "accion": ""
        }},
        "habilidades_blandas": {{
            "nivel": "",
            "accion": ""
        }},
        "lenguaje_tecnico": {{
            "nivel": "",
            "accion": ""
        }}
    }}

    Todo en base al siguiente contenido del CV:
    \"\"\"{contenido}\"\"\"
    """

    response10 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt10}],
        temperature=0.7,
        #max_tokens=50  
    )
    ajuste_puesto = response10['choices'][0]['message']['content']
    # try:
    #     ajuste_puesto_json = clean_and_load_json(ajuste_puesto)
    # except json.JSONDecodeError as e:
    #     print("Error al decodificar JSON:", e)
    #     ajuste_puesto_json = None
    print(ajuste_puesto)


    prompt11 = f"""
        Brinda sugerencias personalizadas de mejora por sección del CV, orientadas al rol de {puesto}.

        En esta parte, cubre lo siguiente:

        - En "Empresa" indica el nombre de la empresa tal como aparece en el CV. Identificalo bien porfavor. No confundir con el rol. 
        - En "Actual" incluye el texto completo de la experiencia laboral tal como figura en el CV.
        - En "Recomendado" proporciona una versión mejorada del texto de experiencia laboral, aplicando el siguiente formato:

            Logro profesional + Elemento de descripción de trabajo + Cómo contribuyó a la empresa + % o cifra específica (si aplica).

            Además:
            - Inicia con un verbo de acción fuerte.
            - Alinea el contenido con las funciones o competencias clave para el rol de {puesto}.
            - Usa el contenido original como base, no inventes logros no mencionados.
            - Mejora redacción, impacto y claridad, sin agregar información no contenida en el texto original.

        Devuélveme solo un JSON con el siguiente formato:

        [
        {{
            "Empresa": "Nombre de la empresa",
            "Actual": "Texto original tal como aparece en el CV. El nombre del puesto y su descripción.",
            "Recomendado": "Texto mejorado aplicando el formato indicado y orientado al puesto de {puesto}."
        }},
        {{
            "Empresa": "Nombre de la empresa",
            "Actual": "Texto original tal como aparece en el CV. El nombre del puesto y su descripción.",
            "Recomendado": "Texto mejorado aplicando el formato indicado y orientado al puesto de {puesto}."
        }}
        ]

        Solo analiza la sección de experiencia laboral.  
        NO INCLUYAS EDUCACION. SI SOLO HAY UNA EXPERIENCIA LABORAL, DEVUELVE UN JSON CON UN SOLO OBJETO.  
        Si no hay experiencia laboral, devuelve un JSON con un único objeto que indique que no se encontró experiencia laboral.
        No incluyas encabezados, datos de contacto ni formación académica.  
        No agregues explicaciones fuera del JSON.  
        Toda la información debe basarse únicamente en el contenido proporcionado a continuación:

        \"\"\"{contenido}\"\"\"
    """
    response11 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt11}],
        temperature=0.7,
        #max_tokens=50  
    )
    experiencia_laboral = response11['choices'][0]['message']['content'].strip()

    prompt12 = f"""
    Actúa como un experto en reclutamiento y redacción de currículums (CVs), con experiencia en múltiples industrias y perfiles profesionales.

    Analiza el siguiente contenido extraído de un CV:

    \"\"\"{contenido}\"\"\"

    El puesto objetivo del candidato es: **{puesto}**

    Tu tarea es:
    1. Identificar la sección relacionada con habilidades técnicas, herramientas, conocimientos técnicos o específicos del perfil (ej. software, metodologías, idiomas, maquinaria, plataformas, etc.).
    2. Evaluar si esta sección está bien redactada, clara, agrupada correctamente y alineada con el perfil profesional del puesto objetivo (**{puesto}**).
    3. Brindar un conjunto de recomendaciones útiles para mejorar esa sección con el fin de hacerla más atractiva y profesional para un reclutador en ese campo.

    Las recomendaciones pueden incluir:
    - Cómo agrupar las herramientas o habilidades de forma más clara y lógica (por categorías, niveles de dominio, frecuencia de uso, etc.).
    - Cómo mejorar la redacción para evitar repeticiones, ambigüedades o estructuras confusas.
    - Qué tipo de habilidades podrían estar faltando según el rol (sin inventar, pero con sugerencias realistas).
    - Cómo posicionar esa sección en el CV (ej. destacarla si es muy relevante para el rol).
    - Sugerencias de orden (ej. por prioridad, nivel de experiencia o herramientas más demandadas).
    - Qué evitar (exceso de herramientas irrelevantes o tecnológicamente obsoletas).
    - Solo dame 4 recomendaciones
    El tono de las recomendaciones deben ser exhortativas, como si estuvieras dando consejos prácticos al candidato. no usar verbos infinitivos mas si, orientados a resultados.

    Tu respuesta debe ser exclusivamente en formato JSON, con la siguiente estructura:

    {{
    "recomendaciones": [
        "Primera recomendación clara y específica.",
        "Segunda recomendación relevante y alineada al rol {puesto}.",
        "... (tantas como correspondan, mínimo 3 si es posible)"
    ]
    }}

    """

    response12 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt12}],
        temperature=0.7,
        #max_tokens=50
    )

    habilidades_herramientas = response12['choices'][0]['message']['content'].strip()

    prompt13 = f"""
    Analiza el siguiente CV y enfócate exclusivamente en la sección de educación o formación académica.

    Genera un array de recomendaciones generales en formato JSON. Estas recomendaciones deben:

    - Ser útiles y aplicables para mejorar la presentación y claridad de la formación académica.
    - Cada recomendación debe tener como minimo 20 palabras. El tono de las recomendaciones deben ser exhortativas, como si estuvieras dando consejos prácticos al candidato. no usar verbos infinitivos mas si, orientados a resultados. Haz recomendaciones puntuales y específicas, segun el puesto.
    - No inventes información no presente en el CV. Enfocado al puesto de {puesto}. 
    - Si no hay una sección de educación/formación académica en el CV, incluye una única recomendación indicando que dicha sección no fue encontrada. no usar verbos infinitivos mas si, orientados a resultados
    - Solo dame 4 recomendaciones
    Analiza este contenido:

    \"\"\"{contenido}\"\"\"

    Devuelve solo el JSON con este formato:

    [
    "Recomendación 1...",
    "Recomendación 2...",
    ...
    ]
    """

    response13 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt13}],
        temperature=0.7,
        #max_tokens=50  
    )
    educacion = response13['choices'][0]['message']['content']


    prompt14= f"""
    Analiza el siguiente CV y detecta si hay una sección de voluntariado.
    Sino encuentras la sección de voluntariado, responde con un JSON indicando que no se encontró. SE MUY ESPECIFICO Y NO INVENTES INFORMACIÓN. NI LA CONFUNDAS CON EXPERIENCIA LABORAL. SE LITERALMENTE ESPECIFICO CON "VOLUNTARIADO".

    Si existe, por cada experiencia encontrada devuelve:

    - "Organización": nombre de la institución u organización.
    - "Actual": texto original tal como aparece en el CV.
    - "Recomendado": versión mejorada del texto, manteniendo la experiencia pero:
        - Iniciando con un verbo de acción potente.
        - Destacando logros, impacto o habilidades desarrolladas.
        - Enfocando el texto en competencias alineadas al rol de {puesto}.
        - Sin inventar contenido no presente en el CV.

    Si **no se encuentra** una sección de voluntariado, responde igualmente con un JSON en este formato:
    [
    {{
        "Organización": null,
        "Actual": null,
        "Recomendado": "No se encontró una sección de voluntariado en el CV."
    }}
    ]

    Todo el análisis se basa únicamente en el contenido proporcionado a continuación:

    \"\"\"{contenido}\"\"\"

    No incluyas texto fuera del JSON.
    """
    response14 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt14}],
        temperature=0.7,
        #max_tokens=50  
    )
    voluntariado = response14['choices'][0]['message']['content']
    try:
        voluntariado_json = clean_and_load_json(voluntariado)
    except json.JSONDecodeError as e:
        print("Error al decodificar JSON:", e)
        voluntariado_json = None


    prompt15 = f"""
    Actúa como un experto en revisión profesional de currículums (CVs), con énfasis en formato, claridad y atracción para reclutadores. Tienes que responder de tu a tu a un candidato que busca mejorar su CV para el puesto de **{puesto}**.

    Evalúa el siguiente contenido extraído de un CV:

    \"\"\"{contenido}\"\"\"

    El rol objetivo es: **{puesto}**

    Tu tarea es analizar el formato del CV con base en los siguientes criterios, orientados a mejorar su presentación y efectividad:

    1. **Longitud**: Evalúa si el CV excede 1 página (en perfiles junior o intermedios) o si es innecesariamente largo para el rol. el num de paginas es {num_paginas} . recuerda que un CV debe ser conciso y fácil de leer. si es 1 hoja el estado es "Alto", si es 2 hojas "Medio" y si es más de 2 "Bajo".

    2. **Foto**: Verifica si el CV incluye una foto. La mayoría de los filtros automáticos de RRHH no lo recomiendan, especialmente en países donde se evita por sesgos. ENtonces, si hay foto el estado es "Bajo", si no hay foto el estado es "Alto". 
    
    3. **Palabras clave**: Evalúa si incluye términos relevantes al puesto, como tecnologías, habilidades técnicas, o conceptos específicos (por ejemplo, en el caso de {puesto}, busca términos como: análisis de riesgo, scoring, producto financiero, gestión, liderazgo, procesos, herramientas, etc.).
    4. **Verbos de impacto**: Evalúa si se utilizan verbos potentes y orientados a resultados, como: "lideré", "implementé", "optimizé", "logré", en lugar de verbos vagos o pasivos como "encargado de", "apoyé", "participé".

    Para cada uno de estos 4 criterios, responde con:

    -"estado"`: Puede ser **"Alto"**, **"Medio"** o **"Bajo"**, según la calidad o presencia del elemento.
    - "sugerencia"`: Hablame de tu a tu, dime algo como La longitud de tu CV es adecuada, o La foto que subiste no es necesaria en un CV, o Te recomiendo incluir más palabras clave relacionadas con el puesto de {puesto}, o Usa verbos de impacto para destacar tus logros. pero de tu a tu, que se sienta que es un consejo profesional directo, maximo 30 palabras.

    Devuelve exclusivamente un JSON con el siguiente formato:

    {{
    "longitud": {{
        "estado": "",
        "sugerencia": ""
    }},
    "foto": {{
        "estado": "",
        "sugerencia": ""
    }},
    "palabras_clave": {{
        "estado": "",
        "sugerencia": ""
    }},
    "verbos_de_impacto": {{
        "estado": "",
        "sugerencia": ""
    }}
    }}
    """
    response15 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt15}],
        temperature=0.7,
        #max_tokens=50  
    )
    formato_optimizacion = response15['choices'][0]['message']['content']


    # PROMPT ADICIONALES

    prompt_feedback_summary = f"""
    Eres un reclutador profesional. A continuación, se muestra el contenido del CV de un candidato para el puesto de {puesto}. Por favor, proporciona un resumen general del feedback para el candidato, considerando los siguientes aspectos:

    - La calidad general del CV, incluyendo su claridad y profesionalismo.
    - La relevancia de la experiencia laboral para el puesto al que está aplicando.
    - La adecuación de las habilidades técnicas y blandas para el puesto.
    - Cualquier área de mejora significativa o notoria en el CV.
    - La estructura general del CV y su legibilidad.

    Tu tarea es resumir el feedback en un párrafo breve, claro y directo. No incluyas detalles extensos ni repitas información ya mencionada, mantén el análisis conciso y práctico.

    Contenido del CV a evaluar:
    {contenido}
    """

    response_feedback_summary = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt_feedback_summary}],
        temperature=0.7,
        # max_tokens=150  # Puedes ajustar los tokens si necesitas una respuesta más larga o más corta
    )

    feedback_summary = response_feedback_summary['choices'][0]['message']['content'].strip()

    def safe_json_load(data):
        try:
            # Intentamos cargar el JSON
            return json.loads(data)
        except json.JSONDecodeError:
            # Si ocurre un error, retornamos None o el valor que prefieras
            return None
        
    def process_formatting_response(response):
    # Intentar extraer la respuesta en formato JSON
        formatting_data = safe_json_load(response)

        # Si la respuesta no tiene el formato correcto, crear una estructura predeterminada
        if formatting_data is None or "formattingAndLanguage" not in formatting_data:
            formatting_data = {
                "formattingAndLanguage": {
                    "clarity": "No disponible",
                    "professionalism": "No disponible",
                    "grammarSpellingErrorsCount": 0,
                    "actionVerbsUsed": False
                }
            }

        # Asegurarse de que todas las claves estén presentes
        formatting_data["formattingAndLanguage"].setdefault("clarity", "No disponible")
        formatting_data["formattingAndLanguage"].setdefault("professionalism", "No disponible")
        formatting_data["formattingAndLanguage"].setdefault("grammarSpellingErrorsCount", 0)
        formatting_data["formattingAndLanguage"].setdefault("actionVerbsUsed", False)

        return formatting_data
        
    def process_keywords_response(response):
        # Intentar extraer la respuesta en formato JSON
        keywords_data = safe_json_load(response)

        # Si la respuesta no tiene el formato correcto, crear una estructura predeterminada
        if keywords_data is None or "keywordAnalysis" not in keywords_data:
            keywords_data = {
                "keywordAnalysis": {
                    "jobKeywordsFound": [],
                    "jobKeywordsMissing": [],
                    "generalSkillsKeywordsFound": []
                }
            }

        # Asegurarse de que todas las claves estén presentes
        keywords_data["keywordAnalysis"].setdefault("jobKeywordsFound", [])
        keywords_data["keywordAnalysis"].setdefault("jobKeywordsMissing", [])
        keywords_data["keywordAnalysis"].setdefault("generalSkillsKeywordsFound", [])

        return keywords_data

    prompt_formatting = f"""
    Eres un reclutador profesional. A continuación, se muestra el contenido del CV de un candidato para el puesto de {puesto}. 
    Por favor, proporciona un análisis detallado sobre el formato y lenguaje del CV, evaluando lo siguiente:

    1. Claridad del CV: ¿Es fácil de leer y entender? ¿La información está organizada de manera clara?
    2. Profesionalismo: ¿El CV tiene un aspecto profesional? ¿La tipografía y el diseño son adecuados?
    3. Errores gramaticales y ortográficos: ¿Cuántos errores gramaticales y ortográficos hay en el CV?
    4. Uso de verbos de acción: ¿Se utilizan verbos de acción en las descripciones de las experiencias laborales? ¿Son adecuados para resaltar logros?

    Formato de salida: 
    {{
        "formattingAndLanguage": {{
            "clarity": "string_evaluacion_claridad",
            "professionalism": "string_evaluacion_profesionalismo",
            "grammarSpellingErrorsCount": "number_cantidad_errores",
            "actionVerbsUsed": "boolean"
        }}
    }}

    Contenido del CV a evaluar:
    {contenido}
    """

    response_formatting = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt_formatting}],
        temperature=0.7,
    )
    formatting = process_formatting_response(response_formatting['choices'][0]['message']['content'])

    prompt_keywords = f"""
    Eres un reclutador profesional. A continuación, se muestra el contenido del CV de un candidato para el puesto de {puesto}. 
    Por favor, extrae las palabras clave relevantes para el puesto en cuestión y las habilidades generales mencionadas en el CV. 

    Primero, identifica las palabras clave relacionadas con el puesto de {puesto}, estas pueden ser habilidades técnicas, habilidades blandas o certificaciones que son relevantes para el rol. Luego, clasifica las palabras clave en las siguientes categorías:

    1. **Palabras clave encontradas**: Las palabras clave relacionadas con el puesto que aparecen en el CV.
    2. **Palabras clave faltantes**: Las palabras clave que son esenciales para el puesto pero no aparecen en el CV.
    3. **Palabras clave de habilidades generales encontradas**: Las habilidades generales que son valiosas para el rol (por ejemplo: comunicación, trabajo en equipo, etc.).

    Formato de salida: 
    {{
        "keywordAnalysis": {{
            "jobKeywordsFound": ["palabra_clave_1", "palabra_clave_2"],
            "jobKeywordsMissing": ["palabra_clave_faltante_1"],
            "generalSkillsKeywordsFound": ["habilidad_general_1"]
        }}
    }}

    Contenido del CV a evaluar:
    {contenido}
    """

    response_keywords = openai.ChatCompletion.create(
    model="gpt-3.5-turbo", 
    messages=[{"role": "user", "content": prompt_keywords}],
    temperature=0.7,
    )

    keywords = process_keywords_response(response_keywords['choices'][0]['message']['content'])

    prompt_error_analysis = f"""
    Eres un reclutador profesional. A continuación, analiza el siguiente currículum vitae para identificar los errores más comunes que se presentan en este documento. Los errores pueden incluir:
    - Errores de formato
    - Errores ortográficos
    - Secciones mal estructuradas
    - Información innecesaria o faltante
    - Uso incorrecto de la tipografía o la organización visual

    Por favor, lista todos los errores comunes que encuentres en el CV y devuélvelos como una lista de errores. Cada error debe estar separado por guiones (-). No agregues información adicional.

    {contenido}
    """
    response_error_analysis = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt_error_analysis}],
        temperature=0.7,
    )

    errores_comunes = response_error_analysis['choices'][0]['message']['content'].strip()

    def process_ats_response(response):
        # Intentar extraer la respuesta en formato JSON
        ats_data = safe_json_load(response)

        # Si la respuesta no tiene el formato correcto, crear una estructura predeterminada
        if ats_data is None or "atsCompliance" not in ats_data:
            ats_data = {
                "atsCompliance": {
                    "score": 0,
                    "issues": [],
                    "recommendations": []
                }
            }

        # Asegurarse de que todas las claves estén presentes
        ats_data["atsCompliance"].setdefault("score", 0)
        ats_data["atsCompliance"].setdefault("issues", [])
        ats_data["atsCompliance"].setdefault("recommendations", [])

        return ats_data
    
    prompt_fortaleza = f"""
    Eres un reclutador profesional. A continuación, analiza el siguiente currículum vitae para identificar las fortalezas más comunes que se presentan en este documento. Los errores pueden incluir:
   
    Por favor, lista todos las fortalezas comunes que encuentres en el CV y devuélvelos como una lista de errorfortalezases. Cada fortalezas debe estar separado por guiones (-). No agregues información adicional.

    {contenido}
    """

    respon_fortaleza = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt_fortaleza}],
        temperature=0.7,
    )

    fortalezas = respon_fortaleza['choices'][0]['message']['content'].strip()

    prompt_ats_compliance = f"""
    Eres un reclutador profesional con experiencia en el uso de sistemas de seguimiento de candidatos (ATS). A continuación, se muestra el contenido del CV de un candidato para el puesto de {puesto}. 
    Por favor, evalúa el cumplimiento del CV con respecto a los criterios comunes de un sistema ATS. 

    Tu tarea es realizar lo siguiente:

    1. **Puntaje de Cumplimiento ATS (de 0 a 100)**: Evalúa el grado de cumplimiento del CV con los criterios comunes de los sistemas ATS, como el uso de palabras clave, la legibilidad, el formato, y la estructura.
    2. **Problemas encontrados**: Proporciona una lista de los problemas comunes detectados en el CV en relación con el cumplimiento de los estándares ATS. Algunos problemas pueden incluir:
        - Uso insuficiente de palabras clave relacionadas con el puesto.
        - Formato inapropiado o no compatible con el ATS.
        - Mala organización de la información.
        - Información irrelevante o mal estructurada.
        - Falta de secciones claves como experiencia, habilidades, educación.
    3. **Recomendaciones para mejorar el cumplimiento ATS**: Brinda sugerencias sobre cómo mejorar el CV para cumplir mejor con los requisitos de un sistema ATS. Las recomendaciones deben ser prácticas y concretas.

    Formato de salida: 
    {{
        "atsCompliance": {{
            "score": "number_puntaje_ats_0_100",
            "issues": ["problema_ats_1", "problema_ats_2"],
            "recommendations": ["sugerencia_ats_1"]
        }}
    }}

    Contenido del CV a evaluar:
    {contenido}
    """

    response_ats_compliance = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt_ats_compliance}],
        temperature=0.7,
    )

    ats_compliance = process_ats_response(response_ats_compliance['choices'][0]['message']['content'])

    
    def process_skills_response(response):
        # Intenta extraer la respuesta en formato JSON
        skills_data = safe_json_load(response)

        # Si la respuesta no tiene el formato correcto, ajustarlo
        if skills_data is None or "skills" not in skills_data:
            # Crear un objeto vacío para asegurar la estructura
            skills_data = {
                "skills": {
                    "technical": [],
                    "soft": [],
                    "languages": []
                }
            }

        # Asegurarte de que las secciones estén presentes, aunque sean listas vacías
        skills_data["skills"].setdefault("technical", [])
        skills_data["skills"].setdefault("soft", [])
        skills_data["skills"].setdefault("languages", [])

        return skills_data


    prompt_skills = f"""
    Eres un reclutador profesional. A continuación, se muestra el contenido del CV de un candidato para el puesto de {puesto}. 
    Por favor, extrae las habilidades técnicas, habilidades blandas e idiomas mencionados en el CV. 

    Proporciona los datos de la siguiente manera, asegurándote de que cada sección esté bien organizada:

    - Habilidades Técnicas: [Lista de habilidades técnicas]
    - Habilidades Blandas: [Lista de habilidades blandas]
    - Idiomas: [Lista de idiomas con niveles de dominio]

    Ejemplo de formato correcto:

    {{
        "skills": {{
            "technical": [
                "Python",
                "JavaScript"
            ],
            "soft": [
                "Comunicación",
                "Trabajo en equipo"
            ],
            "languages": [
                "Inglés (Avanzado)",
                "Español (Nativo)"
            ]
        }}
    }}

    Contenido del CV a evaluar:
    {contenido}
    """

    response_skills = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt_skills}],
        temperature=0.7,
    )
    
    skills = process_skills_response(response_skills['choices'][0]['message']['content'])


    prompt_education = f"""
    Eres un reclutador profesional. A continuación, se muestra el contenido del CV de un candidato para el puesto de {puesto}. Por favor, extrae la información relacionada con la educación. Para cada título educativo, proporciona la siguiente información de manera estructurada en JSON:

    - Grado: El título académico obtenido por el candidato (por ejemplo, Licenciatura en Ingeniería de Sistemas).
    - Institución: El nombre de la institución educativa en la que el candidato obtuvo su título.
    - Año de graduación: El año de graduación o la fecha en la que el candidato completó sus estudios.

    Formato JSON:
    {{
        "education": [
            {{
                "degree": "Título obtenido",
                "institution": "Institución educativa",
                "graduationYear": "Año de graduación"
            }}
        ]
    }}

    Contenido del CV a evaluar:
    {contenido}
    """

    response_education = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt_education}],
        temperature=0.7,
    )

    # Extrae la información de educación desde la respuesta
    education_data = response_education['choices'][0]['message']['content']

    # Asegúrate de que la respuesta esté en formato JSON válido
    education_data_json = safe_json_load(education_data)

    # Si no se pudo parsear correctamente, podrías intentar nuevamente o manejar el error
    if education_data_json is None:
        return await analizar_cv(pdf_url, puesto_postular)

    # Extraer la educación del JSON
    education = education_data_json.get("education", [])

    # Ahora puedes hacer algo con el JSON válido que contiene la información de la educación


    logo_url = "https://myworkin.pe/MyWorkIn-web.png"  # Cambia esto si necesitas una URL dinámica
    ruta_logo = "static/analisis_pdfs/logo.png"  # Carpeta donde se guardará el logo
    ruta_logo2 = "static/analisis_pdfs/MyWorkIn 2.png"  # Carpeta donde se guardará el logo

    descargar_imagen(logo_url, ruta_logo)

    phone = extract_phone(contenido)
    linkedin = extract_linkedin(contenido)
    address = extract_address(contenido)

    raw_text = contenido  # Aquí, 'contenido' ya es el texto completo del CV extraído

    parsed = json.loads(mainly_analysis)  # Convierte el string JSON en un diccionario
    overall_score = f"{parsed['porcentaje']}/10"

    nombre_pdf = f"analisis_cv_{int(datetime.timestamp(datetime.now()))}.pdf"
    ruta_completa = 'https://api-cv-210j.onrender.com/static/analisis_pdfs/'+nombre_pdf
    resultados = {
        "nombre": json.loads(candidate_name),
        "mainly_analysis": json.loads(mainly_analysis),
        "pagination": json.loads(pagination),
        "spelling": json.loads(spelling),
        "filename": json.loads(filename_response),
        "indispensable": json.loads(indispensable),
        "repeat_words": json.loads(repeat_words),
        "relevance": relevance,
        "verbos_impact": json.loads(verbos_impact),
        "perfil_profesional": json.loads(perfil_profesional),
        "ajuste_puesto": json.loads(ajuste_puesto),
        "experiencia_laboral": json.loads(experiencia_laboral),
        "habilidades_herramientas": json.loads(habilidades_herramientas)['recomendaciones'],
        "educacion": json.loads(educacion),
        "voluntariado": voluntariado_json,
        "formato-optimizacion": json.loads(formato_optimizacion),
        "puesto_postular": puesto,
        "status": "success", 
        "message": "CV procesado y análisis guardado exitosamente.",
        "analysis_id": generate_analysis_id(candidate_name),
        "extractedData": {

            "cvAnalysisId": generate_analysis_id(candidate_name),
            "userId": generate_user_id(candidate_name),
            "jobPositionApplied": puesto, 
            "cvOriginalFileUrl": original_pdf,
            "analysisDateTime": analysis_datetime,  # Aquí agregamos la fecha y hora
            "processingTimeMs": processing_time_ms,  # Aq
            "extractedData": { 
                "candidateName": json.loads(candidate_name)['nombre'],
                "contactInfo": {
                    "email": email if email else "No disponible",  # Aquí agregamos el email extraído
                    "phone": phone,
                    "linkedin": linkedin,
                    "address": address
                },
                "professionalSummary": overall_score,
                "workExperience": json.loads(experiencia_laboral),

                "education": education,
                "skills": skills["skills"],
                "rawText": raw_text,
            },
            "analysisResults": { 
                "pdf_url": ruta_completa,
                "overallScore": f"{parsed['porcentaje']}/10",
                "atsCompliance": ats_compliance["atsCompliance"],
                "strengths": fortalezas,
                "areasForImprovement": errores_comunes, 
                "keywordAnalysis": keywords["keywordAnalysis"],
                "formattingAndLanguage": formatting["formattingAndLanguage"],
                "feedbackSummary": feedback_summary  # Aquí agregamos el feedback summary
            }
        },
    }

    # Generar el PDF y obtener la ruta
    ruta_pdf = generar_pdf_con_secciones(resultados, nombre_pdf, ruta_logo,ruta_logo2)  # Aquí pasamos la ruta del logo

    # Agregar la ruta del PDF al JSON de la respuesta
    resultados["pdf_evaluado"] = ruta_pdf

    return JSONResponse(content=resultados)


def descargar_imagen(url: str, ruta_local: str):
    response = requests.get(url)
    if response.status_code == 200:
        with open(ruta_local, "wb") as f:
            f.write(response.content)
        print("Imagen descargada correctamente.")
    else:
        print(f"Error al descargar la imagen: {response.status_code}")


def dibujar_velocimetro(c, centro_x, centro_y, radio, valor):
    """
    Dibuja un velocímetro semicírculo (tipo 7.8/10) en un canvas de ReportLab.

    :param c: canvas de ReportLab
    :param centro_x: coordenada x del centro del velocímetro
    :param centro_y: coordenada y del centro del velocímetro
    :param radio: radio del semicírculo
    :param valor: valor entre 0 y 10
    """
    # Aseguramos que el valor esté en rango
    valor = max(0, min(10, valor))

    # Determinar color según valor
    if valor <= 3:
        color_arco = colors.red
    elif valor < 7:
        color_arco = colors.orange
    else:
        color_arco = colors.green

    # Parámetros del ángulo
    angulo_total = 180  # grados
    angulo_inicio = 180  # desde la izquierda
    angulo_valor = angulo_total * (valor / 10)

    # Estilo de línea
    c.setLineWidth(15)

    # 1. Arco de fondo gris claro
    c.setStrokeColorRGB(0.9, 0.9, 0.95)
    c.arc(centro_x - radio, centro_y - radio, centro_x + radio, centro_y + radio,
          startAng=angulo_inicio, extent=-angulo_total)

    # 2. Arco coloreado según valor
    c.setStrokeColor(color_arco)
    c.arc(centro_x - radio, centro_y - radio, centro_x + radio, centro_y + radio,
          startAng=angulo_inicio, extent=-angulo_valor)

    # 3. Círculo al final del arco
    angulo_final = angulo_inicio - angulo_valor
    angulo_final_rad = np.radians(angulo_final)
    punto_x = centro_x + radio * cos(angulo_final_rad)
    punto_y = centro_y + radio * sin(angulo_final_rad)
    c.setFillColor(color_arco)
    c.circle(punto_x, punto_y, 8, fill=1)

    # 4. Texto central del valor
    c.setFont("Poppins-Bold", 18)
    c.setFillColor(colors.black)
    c.drawCentredString(centro_x, centro_y + 10, f"{valor:.1f}/10")

    # 5. Texto secundario
    c.setFont("Poppins-Regular", 10)
    c.setFillColor(colors.grey)
    c.drawCentredString(centro_x, centro_y - 5, "Puntaje General")


def wrap_text(text, max_width, canvas, font_name, font_size):
    """Divide un texto en líneas para que no exceda max_width."""
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if stringWidth(test_line, font_name, font_size) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

# 1. Encabezado con logo y título
def seccion_encabezado(c, ancho, alto, logo_path):
    logo_width = 120
    logo_height = 26
    c.drawImage(logo_path, 20, alto - 35, width=logo_width, height=logo_height, mask='auto')

    texto = "Informe de revisión de CV"
    c.setFont("Poppins-Bold", 14)
    texto_ancho = c.stringWidth(texto, "Poppins-Bold", 14)
    x_texto = ancho - 25 - texto_ancho
    y_texto = alto - 27
    c.drawString(x_texto, y_texto, texto)

# 2. Sección 2 (ejemplo)

def seccion_2(c, ancho, alto, y_inicio, datos_cv):
    analisis = datos_cv.get('mainly_analysis', {}).get('analisis', 'Análisis no disponible')
    porcentaje = datos_cv.get('mainly_analysis', {}).get('porcentaje', 0)
    nombre = datos_cv.get('nombre', {}).get('nombre', 'nombre no disponible')
    puesto_postular = datos_cv.get('puesto_postular', 'puesto_postular no disponible')

    alto_degradado = 250   # altura menor para el fondo degradado
    alto_rectangulo = 380  # altura mayor para el rectángulo blanco

    margen_horizontal = 30
    padding_interno = 20
    sombra_offset = 5

    # Cargar imagen
    imagen_fondo = ImageReader('./public/img/fondo.png')

    # Dibujar imagen de fondo con las dimensiones deseadas
    c.drawImage(imagen_fondo, 0, y_inicio - alto_degradado, width=ancho, height=alto_degradado)

    # 2. Dimensiones y posición del div con sombra y rectángulo blanco (mayor altura)
    x_div = margen_horizontal + padding_interno
    y_div = y_inicio - alto_rectangulo + 20 + padding_interno
    ancho_div = ancho - 2 * margen_horizontal - 2 * padding_interno
    alto_div = alto_rectangulo - 20 - 2 * padding_interno

    # 3. Sombra (ligeramente desplazada)
    c.setFillColorRGB(0, 0, 0, alpha=0.15)
    c.roundRect(x_div + sombra_offset, y_div - sombra_offset,
                ancho_div, alto_div, radius=15, fill=1, stroke=0)

    # 4. Rectángulo blanco redondeado (div principal)
    c.setFillColor(colors.white)
    c.roundRect(x_div, y_div, ancho_div, alto_div, radius=15, fill=1, stroke=0)

    # 5. Texto principal centrado dentro del rectángulo
    c.setFillColor(colors.black)
    c.setFont("Poppins-Bold", 16)
    texto_principal = nombre
    texto_ancho = c.stringWidth(texto_principal, "Poppins-Regular", 14)
    text_x = x_div + (ancho_div - texto_ancho) / 2
    text_y = y_div + alto_div - 40
    c.drawString(text_x, text_y, texto_principal)

    # Texto secundario (puesto a postular ajustado)
    c.setFillColor(colors.grey)
    c.setFont("Poppins-Regular", 10)

    # Usamos wrap_text para ajustar el puesto a postular en una línea o dividirlo
    lineas_secundarias = wrap_text(puesto_postular, ancho_div - 2 * padding_interno, c, "Poppins-Regular", 10)
    line_height = 14
    y_texto_secundario = text_y - 15

    # Dibujar las líneas de texto secundario ajustadas
    for i, linea in enumerate(lineas_secundarias):
        ancho_linea = c.stringWidth(linea, "Poppins-Regular", 10)
        x_linea = x_div + (ancho_div - ancho_linea) / 2
        y_linea = y_texto_secundario - i * line_height
        c.drawString(x_linea, y_linea, linea)

    # 6. Velocímetro dentro del div blanco
    centro_x = x_div + ancho_div / 2
    espacio_antes_velocimetro = 5
    centro_y = y_div + alto_div / 2 - espacio_antes_velocimetro
    radio = 80
    valor = porcentaje / 10  # Divide el porcentaje entre 10 para obtener el valor adecuado

    # Asumo que tienes la función dibujar_velocimetro definida en otro lado
    dibujar_velocimetro(c, centro_x, centro_y, radio, valor)

    espacio_despues_velocimetro = 30

    # Determinar palabra clave y color según valor
    if valor < 4:
        palabra_estado = "desaprobado!"
        color_estado = colors.red
    elif valor < 7:
        palabra_estado = "observado!"
        color_estado = colors.orange
    else:
        palabra_estado = "aprobado!"
        color_estado = colors.green

    texto_base = "Tu CV está "
    fuente = "Poppins-Bold"
    tamano_fuente = 14

    ancho_base = c.stringWidth(texto_base, fuente, tamano_fuente)
    ancho_estado = c.stringWidth(palabra_estado, fuente, tamano_fuente)
    ancho_total = ancho_base + ancho_estado

    text_x = x_div + (ancho_div - ancho_total) / 2
    text_y = centro_y - radio + espacio_despues_velocimetro

    c.setFont(fuente, tamano_fuente)
    c.setFillColor(colors.black)
    c.drawString(text_x, text_y, texto_base)

    c.setFillColor(color_estado)
    c.drawString(text_x + ancho_base, text_y, palabra_estado)

    # 7. Reemplazar texto adicional con el análisis
    c.setFont("Poppins-Regular", 10)
    c.setFillColor(colors.darkgray)

    # Mantener la posición del análisis, pero justificar el texto
    estilo_analisis = ParagraphStyle(
        name="AnalisisJustificado",
        fontName="Poppins-Regular",
        fontSize=10,
        leading=12,
        alignment=TA_JUSTIFY,  # Justificar el texto
        spaceBefore=25,
        spaceAfter=5,
    )

    # Crear el párrafo con el análisis justificado
    par_analisis = Paragraph(analisis, estilo_analisis)
    w_analisis, h_analisis = par_analisis.wrap(ancho_div - 2 * padding_interno, alto_div)

    # Ajustar la posición para dibujarlo justo debajo del velocímetro
    y_analisis_pos = centro_y - radio - espacio_despues_velocimetro - 10  # Ajuste la posición aquí
    par_analisis.drawOn(c, x_div + padding_interno, y_analisis_pos)

    x_texto = margen_horizontal
    y_texto = y_inicio - 30  # A
    c.setFont("Poppins-Regular", 12)
    c.setFillColor(colors.black)
    altura_ocupada = 340  # altura total usada por la sección
    return altura_ocupada


def seccion_3(c, ancho, alto, y_inicio, datos_cv):
    # Asegurarse de que 'paginas' sea una cadena
    paginas = str(datos_cv.get('pagination', {}).get('paginas', 'Paginas no disponible'))
    comentarioPagination = datos_cv.get('pagination', {}).get('comentario', 'Comentario no disponible')
    
    errores = str(datos_cv.get('spelling', {}).get('errores', 'Paginas no disponible'))
    erroresPagination = datos_cv.get('spelling', {}).get('comentario', 'Comentario no disponible')
    detalles_errores = datos_cv.get('spelling', {}).get('detalle_errores', [])

    margen_horizontal = 50
    espacio_entre_divs = 20
    alto_div = 160

    sombra_expand = 8
    sombra_offset_x = 2
    sombra_offset_y = -2
    sombra_alpha = 0.12

    ancho_disponible = ancho - 2 * margen_horizontal - espacio_entre_divs
    ancho_div = ancho_disponible / 2

    x_div1 = margen_horizontal
    x_div2 = margen_horizontal + ancho_div + espacio_entre_divs
    y_div = y_inicio - alto_div

    # Sombra primer div
    c.setFillColorRGB(0, 0, 0, alpha=sombra_alpha)
    c.roundRect(
        x_div1 - sombra_expand / 2 + sombra_offset_x,
        y_div - sombra_expand / 2 + sombra_offset_y,
        ancho_div + sombra_expand,
        alto_div + sombra_expand,
        radius=15 + sombra_expand / 2,
        fill=1, stroke=0
    )

    # Sombra segundo div
    c.roundRect(
        x_div2 - sombra_expand / 2 + sombra_offset_x,
        y_div - sombra_expand / 2 + sombra_offset_y,
        ancho_div + sombra_expand,
        alto_div + sombra_expand,
        radius=15 + sombra_expand / 2,
        fill=1, stroke=0
    )

    # Div blancos sin borde encima
    c.setFillColor(colors.white)
    c.roundRect(x_div1, y_div, ancho_div, alto_div, radius=15, fill=1, stroke=0)
    c.roundRect(x_div2, y_div, ancho_div, alto_div, radius=15, fill=1, stroke=0)

    # Títulos superiores en gris claro
    c.setFillColor(colors.grey)
    c.setFont("Poppins-SemiBold", 9)
    c.drawString(x_div1 + 20, y_div + alto_div - 15, "Tamaño")
    c.drawString(x_div2 + 20, y_div + alto_div - 15, "Ortografía")

    # Primer div: "paginas Pagina" con colores
    c.setFillColor(colors.black)
    c.setFont("Poppins-Bold", 16)
    ancho_texto_1 = c.stringWidth(paginas, "Poppins-Bold", 16)
    ancho_texto_2 = c.stringWidth("  Pagina", "Poppins-Bold", 16)

    total_ancho = ancho_texto_1 + ancho_texto_2
    inicio_texto = x_div1 + (ancho_div - total_ancho) / 2

    c.drawString(inicio_texto, y_div + alto_div - 40, paginas)
    c.setFillColor(colors.green)
    c.drawString(inicio_texto + ancho_texto_1, y_div + alto_div - 40, "Pagina")

    # Justificación del texto del comentarioPagination
    c.setFillColor(colors.black)
    c.setFont("Poppins-Regular", 9)
    texto_1 = comentarioPagination

    palabras = texto_1.split()
    lineas = []
    linea_actual = ""
    max_ancho = ancho_div - 40

    for palabra in palabras:
        prueba_linea = linea_actual + (" " if linea_actual else "") + palabra
        if c.stringWidth(prueba_linea, "Helvetica", 10) <= max_ancho:
            linea_actual = prueba_linea
        else:
            lineas.append(linea_actual)
            linea_actual = palabra
    if linea_actual:
        lineas.append(linea_actual)

    y_texto = y_div + alto_div - 70
    for linea in lineas:
        ancho_linea = c.stringWidth(linea, "Helvetica", 10)
        x_texto = x_div1 + (ancho_div - ancho_linea) / 2
        c.drawString(x_texto, y_texto, linea)
        y_texto -= 14

    # Segundo div: "Errores" en rojo y texto
    c.setFillColor(colors.black)
    c.setFont("Poppins-Bold", 16)
    ancho_texto_1 = c.stringWidth(errores, "Poppins-Bold", 16)
    ancho_texto_2 = c.stringWidth(" Errores", "Poppins-Bold", 16)

    total_ancho = ancho_texto_1 + ancho_texto_2
    inicio_texto = x_div2 + (ancho_div - total_ancho) / 2

    c.drawString(inicio_texto, y_div + alto_div - 40, errores)
    c.setFillColor(colors.red)
    c.drawString(inicio_texto + ancho_texto_1, y_div + alto_div - 40, " Errores")

    # Justificación del texto de erroresPagination
    c.setFillColor(colors.black)
    c.setFont("Poppins-Regular", 9)
    texto_2 = erroresPagination

    palabras = texto_2.split()
    lineas = []
    linea_actual = ""
    max_ancho = ancho_div - 40

    for palabra in palabras:
        prueba_linea = linea_actual + (" " if linea_actual else "") + palabra
        if c.stringWidth(prueba_linea, "Helvetica", 10) <= max_ancho:
            linea_actual = prueba_linea
        else:
            lineas.append(linea_actual)
            linea_actual = palabra
    if linea_actual:
        lineas.append(linea_actual)

    y_texto = y_div + alto_div - 70
    for linea in lineas:
        ancho_linea = c.stringWidth(linea, "Helvetica", 10)
        x_texto = x_div2 + (ancho_div - ancho_linea) / 2
        c.drawString(x_texto, y_texto, linea)
        y_texto -= 14

    # Mostrar los detalles de los errores con justificación
    estilo_errores = ParagraphStyle(
        name="ErroresJustificados",
        fontName="Poppins-Regular",
        fontSize=8,
        leading=10,
        alignment=TA_JUSTIFY,
        spaceBefore=0,
        spaceAfter=0,
    )

    # Crear un único párrafo con los detalles de los errores separados por comas
    errores_completos = ", ".join([f"{error['original']} → {error['sugerencia']}" for error in detalles_errores])
    par_errores_completos = Paragraph(errores_completos, estilo_errores)

    # Obtener el tamaño del párrafo
    w_error, h_error = par_errores_completos.wrap(ancho_div - 40, alto_div)

    # Dibujar el párrafo completo en la página
    par_errores_completos.drawOn(c, x_div2 + 20, y_texto - h_error)

    # Actualizar la posición Y para los siguientes elementos
    y_texto -= h_error + 5  # Espacio entre los errores

    return alto_div

#SECCION 4 - JUSTIFICADO
def seccion_4(c, ancho, alto, y_inicio, datos_cv):
    archivo = datos_cv.get('filename', {}).get('archivo', 'Archivo no disponible')
    comentario = datos_cv.get('filename', {}).get('comentario', 'Comentario no disponible')

    margen_horizontal = 50
    margen_interno = 15  # margen interno para texto
    alto_div = 130

    sombra_expand = 8
    sombra_offset_x = 2
    sombra_offset_y = -2
    sombra_alpha = 0.12

    ancho_div = ancho - 2 * margen_horizontal
    x_div = margen_horizontal
    y_div = y_inicio - alto_div

    # Sombra
    c.setFillColorRGB(0, 0, 0, alpha=sombra_alpha)
    c.roundRect(
        x_div - sombra_expand / 2 + sombra_offset_x,
        y_div - sombra_expand / 2 + sombra_offset_y,
        ancho_div + sombra_expand,
        alto_div + sombra_expand,
        radius=15 + sombra_expand / 2,
        fill=1, stroke=0
    )

    # Div blanco principal
    c.setFillColor(colors.white)
    c.roundRect(x_div, y_div, ancho_div, alto_div, radius=15, fill=1, stroke=0)

    # Título "Nombre"
    c.setFillColor(colors.grey)
    c.setFont("Poppins-SemiBold", 9)
    x_nombre = x_div + margen_interno
    y_nombre = y_div + alto_div - 20
    c.drawString(x_nombre, y_nombre, "Nombre")

    # Nombre de archivo
    c.setFillColor(HexColor("#007bb6"))
    c.setFont("Poppins-Bold", 14)
    x_titulo = x_div + margen_interno
    y_titulo = y_nombre - 25
    c.drawString(x_titulo, y_titulo, archivo)

    # --- Comentario justificado ---
    # Parámetros para el párrafo
    estilo_coment = ParagraphStyle(
        name="ComentarioJustificado",
        fontName="Poppins-Regular",
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY,
        spaceBefore=0,
        spaceAfter=0,
    )
    ancho_com = ancho_div - 2 * margen_interno
    x_com = x_div + margen_interno

    # Crear el Paragraph
    par_com = Paragraph(comentario, estilo_coment)
    # Ajusta el párrafo al ancho y un alto suficientemente grande
    w_com, h_com = par_com.wrapOn(c, ancho_com, alto_div)

    # Dibujar el párrafo justo debajo del título
    # drawOn usa la esquina inferior izquierda del párrafo,
    # así que ubicamos su base en y_titulo - h_com
    par_com.drawOn(c, x_com, y_titulo - h_com - 5)

    return alto_div

# SECCION 5 - JUSTIFICADO
def seccion_5(c, ancho, alto, y_inicio, datos_cv):
    # Comentario general
    observacion = datos_cv.get('indispensable', {}) \
                        .get('indispensable', {}) \
                        .get('comentario_general', 'comentario_general no disponible')

    # Márgenes y dimensiones
    margen_horizontal = 50
    alto_div = 130
    ancho_div = ancho - 2 * margen_horizontal
    x_div = margen_horizontal
    y_div = y_inicio - alto_div

    # Parámetros de sombra
    sombra_expand = 6
    sombra_offset_x = 2
    sombra_offset_y = -2
    sombra_alpha = 0.12

    # Dibujar sombra
    c.setFillColorRGB(0, 0, 0, alpha=sombra_alpha)
    c.roundRect(
        x_div - sombra_expand / 2 + sombra_offset_x,
        y_div - sombra_expand / 2 + sombra_offset_y,
        ancho_div + sombra_expand,
        alto_div + sombra_expand,
        radius=12 + sombra_expand / 2,
        fill=1, stroke=0
    )

    # Div blanco principal
    c.setFillColor(colors.white)
    c.roundRect(x_div, y_div, ancho_div, alto_div, radius=12, fill=1, stroke=0)

    # Título "Indispensable"
    c.setFillColor(colors.grey)
    c.setFont("Poppins-SemiBold", 9)
    c.drawString(x_div + 10, y_div + alto_div - 14, "Indispensable")

    # Posición inicial de la tabla
    y_tabla_inicio = y_div + alto_div - 40

    # Cabecera de la tabla
    c.setFont("Poppins-SemiBold", 7)
    columnas = [x_div + 10, x_div + 100, x_div + 160, x_div + 220]
    c.setFillColor(colors.black)
    c.drawString(columnas[0], y_tabla_inicio, "Elemento")
    c.drawString(columnas[1], y_tabla_inicio, "¿Existe?")
    c.drawString(columnas[2], y_tabla_inicio, "¿Bien")
    c.drawString(columnas[2], y_tabla_inicio - 13, "posicionado?")
    c.drawString(columnas[3], y_tabla_inicio, "¿Fácil de")
    c.drawString(columnas[3], y_tabla_inicio - 13, "distinguir?")

    # Línea bajo la cabecera
    c.setStrokeColor(HexColor("#B0B0B0"))
    c.setLineWidth(0.7)
    c.line(columnas[0], y_tabla_inicio - 20, columnas[3] + 30, y_tabla_inicio - 20)

    # Filas de datos
    evaluacion = datos_cv.get('indispensable', {}) \
                        .get('indispensable', {}) \
                        .get('evaluacion', [])
    y_filas = [y_tabla_inicio - 30 - 15 * i for i in range(len(evaluacion))]

    c.setFont("Helvetica", 8)
    check = "✔"
    x_check_1 = columnas[1] + 5
    x_check_2 = columnas[2] + 5
    x_check_3 = columnas[3] + 5

    for i, item in enumerate(evaluacion):
        y = y_filas[i]
        # Elemento
        c.setFillColor(colors.black)
        c.drawString(columnas[0], y, item["elemento"])

        # ¿Existe?
        if item.get("existe", False):
            c.setFillColor(HexColor("#006400"))
            c.drawString(x_check_1, y, check)
        else:
            c.setFillColor(colors.red)
            c.drawString(x_check_1, y, "X")

        # ¿Bien posicionado?
        if item.get("bien_posicionado", False):
            c.setFillColor(HexColor("#006400"))
            c.drawString(x_check_2, y, check)
        else:
            c.setFillColor(colors.red)
            c.drawString(x_check_2, y, "X")

        # ¿Fácil de distinguir?
        if item.get("facil_de_distinguir", False):
            c.setFillColor(HexColor("#006400"))
            c.drawString(x_check_3, y, check)
        else:
            c.setFillColor(colors.red)
            c.drawString(x_check_3, y, "X")

        # Línea separadora
        c.setStrokeColor(HexColor("#B0B0B0"))
        c.setLineWidth(0.5)
        c.line(columnas[0], y - 5, columnas[3] + 30, y - 5)

    # Título y Observación justificada
    x_obs = x_div + 290
    y_obs_title = y_div + alto_div - 25
    ancho_obs = ancho_div - (x_obs - x_div) - 15
    alto_obs = y_obs_title - (y_div + 10)

    c.setFont("Poppins-Bold", 9)
    c.setFillColor(colors.red)
    c.drawString(x_obs, y_obs_title, "Observación:")

    estilo_obs = ParagraphStyle(
        name="Justificado",
        fontName="Poppins-Regular",
        fontSize=9,
        leading=11,
        alignment=TA_JUSTIFY,
        spaceAfter=0,
        spaceBefore=0,
    )

    par_obs = Paragraph(observacion, estilo_obs)
    w_com, h_com = par_obs.wrap(ancho_obs, alto_obs)
    par_obs.drawOn(c, x_obs, y_obs_title - h_com - 4)

    return alto_div

# SECCION 6 - JUSTIFICADO
def seccion_6(c, ancho, alto, y_inicio, datos_cv):
    palabras_repetidas = [item['palabra'] for item in datos_cv.get('repeat_words', {}).get('palabras_repetidas', [])]
    relevance = datos_cv.get('relevance', 'Relevancia no disponible')

    margen_horizontal = 50
    espacio_entre_divs = 20
    alto_div = 180

    sombra_expand = 8
    sombra_offset_x = 2
    sombra_offset_y = -2
    sombra_alpha = 0.12

    ancho_disponible = ancho - 2 * margen_horizontal - espacio_entre_divs
    ancho_div = ancho_disponible / 2

    x_div1 = margen_horizontal
    x_div2 = margen_horizontal + ancho_div + espacio_entre_divs
    y_div = y_inicio - alto_div

    # Dibujar sombras
    c.setFillColorRGB(0, 0, 0, alpha=sombra_alpha)
    for x_div in (x_div1, x_div2):
        c.roundRect(
            x_div - sombra_expand/2 + sombra_offset_x,
            y_div - sombra_expand/2 + sombra_offset_y,
            ancho_div + sombra_expand,
            alto_div + sombra_expand,
            radius=15 + sombra_expand/2,
            fill=1, stroke=0
        )

    # Dibujar divs blancos
    c.setFillColor(colors.white)
    c.roundRect(x_div1, y_div, ancho_div, alto_div, radius=15, fill=1, stroke=0)
    c.roundRect(x_div2, y_div, ancho_div, alto_div, radius=15, fill=1, stroke=0)

    # --- Primer div: Palabras repetidas ---
    c.setFillColor(colors.grey)
    c.setFont("Poppins-Bold", 10)
    c.drawString(x_div1 + 15, y_div + alto_div - 25, "Palabras repetidas")

    c.setFont("Poppins-Bold", 9)
    espacio_x = 12
    espacio_y = 6
    radio_burbuja = 12
    color_burbuja = colors.HexColor("#028BBF")
    color_texto = colors.white

    x_actual = x_div1 + 15
    y_actual = y_div + alto_div - 50

    for palabra in palabras_repetidas:
        ancho_palabra = c.stringWidth(palabra, "Poppins-Bold", 9)
        ancho_burbuja = ancho_palabra + 10
        if x_actual + ancho_burbuja > x_div1 + ancho_div - 15:
            x_actual = x_div1 + 15
            y_actual -= radio_burbuja * 2 + espacio_y
        c.setFillColor(color_burbuja)
        c.roundRect(x_actual, y_actual - radio_burbuja, ancho_burbuja, radio_burbuja*2, radius=radio_burbuja, fill=1, stroke=0)
        c.setFillColor(color_texto)
        c.drawString(x_actual + 5, y_actual - radio_burbuja/2 + 3, palabra)
        x_actual += ancho_burbuja + espacio_x

    # --- Segundo div: Relevancia justificada ---
    # Título
    c.setFillColor(colors.grey)
    c.setFont("Poppins-Bold", 10)
    c.drawString(x_div2 + 15, y_div + alto_div - 25, "Relevancia")

    # Definir estilo justificado
    estilo_rel = ParagraphStyle(
        name="RelJustificado",
        fontName="Poppins-Regular",
        fontSize=9,
        leading=10,
        alignment=TA_JUSTIFY,
        spaceBefore=4,
        spaceAfter=0,
    )

    # Crear y dibujar el párrafo de relevancia
    ancho_rel = ancho_div - 30  # margen interno de 15 a cada lado
    x_rel = x_div2 + 15
    y_rel_top = y_div + alto_div - 25 - 14  # 14 pts por altura de línea y espacio antes

    par_rel = Paragraph(relevance, estilo_rel)
    par_rel.wrapOn(c, ancho_rel, alto_div)
    par_rel.drawOn(c, x_rel, y_rel_top - par_rel.height)

    return alto_div

# SECCION 7 - JUSTIFICADO
def seccion_7(c, ancho, alto, y_inicio, datos_cv):
    nivel       = datos_cv.get('verbos_impact', {}).get('nivel', 0)
    comentario  = datos_cv.get('verbos_impact', {}).get('comentario', 'Comentario no disponible')
    sugerencias = datos_cv.get('verbos_impact', {}).get('sugerencias', ['sugerencias no disponible'])

    nivel = max(1, min(10, nivel))

    margen_horizontal = 50
    alto_div          = 330
    sombra_expand     = 8
    sombra_offset_x   = 2
    sombra_offset_y   = -2
    sombra_alpha      = 0.12

    ancho_div = ancho - 2 * margen_horizontal
    x_div     = margen_horizontal
    y_div     = y_inicio - alto_div

    # Sombra y fondo
    c.setFillColorRGB(0, 0, 0, alpha=sombra_alpha)
    c.roundRect(
        x_div - sombra_expand/2 + sombra_offset_x,
        y_div - sombra_expand/2 + sombra_offset_y,
        ancho_div + sombra_expand,
        alto_div + sombra_expand,
        radius=15 + sombra_expand/2,
        fill=1, stroke=0
    )
    c.setFillColor(colors.white)
    c.roundRect(x_div, y_div, ancho_div, alto_div, radius=15, fill=1, stroke=0)

    # Título
    c.setFillColor(colors.grey)
    c.setFont("Poppins-SemiBold", 9)
    c.drawString(x_div + 10, y_div + alto_div - 14, "Verbos de impacto")

    # Barra de impacto
    barra_x      = x_div + 40
    barra_y      = y_div + alto_div - 70
    barra_width  = ancho_div - 80
    barra_height = 20
    n_segments   = 10
    seg_w        = barra_width / n_segments

    colores_segmentos = [
        colors.Color(1,0,0), colors.Color(1,0.3,0), colors.Color(1,0.5,0),
        colors.Color(1,0.7,0), colors.Color(1,0.9,0), colors.Color(0.9,1,0),
        colors.Color(0.7,1,0), colors.Color(0.4,1,0), colors.Color(0.2,1,0),
        colors.Color(0,1,0)
    ]
    for i in range(n_segments):
        c.setFillColor(colores_segmentos[i] if i < nivel else colors.lightgrey)
        c.rect(barra_x + i*seg_w, barra_y, seg_w, barra_height, stroke=0, fill=1)

    # Numeración
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    for i in range(n_segments+1):
        c.drawString(barra_x + i*seg_w - 3, barra_y + barra_height + 5, str(i+1))

    # Flecha indicador
    flecha_x = barra_x + (nivel - 0.5) * seg_w
    flecha_y = barra_y - 12
    p = c.beginPath()
    p.moveTo(flecha_x, flecha_y)
    p.lineTo(flecha_x - 7, flecha_y - 15)
    p.lineTo(flecha_x + 7, flecha_y - 15)
    p.close()
    c.setFillColor(colors.red)
    c.drawPath(p, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(flecha_x, flecha_y - 23, "Tu nivel")

    # Comentario justificado
    estilo_com = ParagraphStyle(
        name="ComentarioJustificado",
        fontName="Poppins-Regular",
        fontSize=9,
        leading=11,
        alignment=TA_JUSTIFY
    )
    par_com = Paragraph(comentario, estilo_com)
    w_com, h_com = par_com.wrap(ancho_div - 40, barra_y - y_div - 40)
    par_com.drawOn(c, x_div + 20, barra_y - 40 - h_com)

    # Sugerencias con fondo ajustado
    estilo_sug = ParagraphStyle(
        name="SugerenciaJustificada",
        fontName="Helvetica",
        fontSize=9,
        leading=10,
        alignment=TA_JUSTIFY
    )
    padding_x      = 10
    padding_y      = 5
    icon_r         = 7
    text_off       = icon_r*3 + 5
    adv_x_start    = x_div + padding_x + 10
    adv_y          = barra_y - 60 - h_com - 20
    bg_width       = ancho_div - 2 * padding_x - 20  # espacio extra 20 pts

    for sugerencia in sugerencias:
        par_sug = Paragraph(sugerencia, estilo_sug)
        wrap_w, wrap_h = par_sug.wrap(bg_width - text_off - padding_x, alto_div)
        # bg position and size
        bg_x = x_div + padding_x
        bg_y = adv_y - wrap_h - padding_y
        bg_h = wrap_h + 2 * padding_y
        c.setFillColor(colors.whitesmoke)
        c.roundRect(bg_x, bg_y, bg_width, bg_h, radius=10, fill=1, stroke=0)
        # bullet icon
        icon_x = bg_x + padding_x
        icon_y = bg_y + bg_h - padding_y - icon_r
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.red)
        c.setLineWidth(2)
        c.circle(icon_x, icon_y, icon_r, fill=1, stroke=1)
        c.setFillColor(colors.red)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(icon_x, icon_y - 5, "!")
        # draw text
        par_sug.drawOn(c, bg_x + text_off, bg_y + padding_y)
        # next block
        adv_y = bg_y - 20

    return alto_div +20

# SECCION 8 - JUSTIFICADO
def seccion_8(c, ancho, alto, y_inicio, datos_cv):
    actual = datos_cv.get('perfil_profesional', {}).get('actual', 'Actual no disponible')
    recomendado = datos_cv.get('perfil_profesional', {}).get('recomendado', 'Recomendado no disponible')

    # Título
    c.setFont("Poppins-Bold", 14)
    c.setFillColor(colors.HexColor("#028BBF"))
    c.drawString(50, y_inicio, "Perfil Profesional")

    # Posicionar encabezados
    y = y_inicio - 30
    c.setFont("Poppins-SemiBold", 10)
    c.setFillColor(colors.HexColor("#A9A9A9"))
    c.drawString(50, y, "Texto Actual")
    c.drawString(ancho / 2 + 10, y, "Texto recomendado")

    # Línea separatoria
    y_linea = y - 3
    c.setLineWidth(1)
    c.setStrokeColor(colors.black)
    c.line(45, y_linea, ancho - 45, y_linea)

    # Preparar estilo justificado para ambos textos
    estilo_col = ParagraphStyle(
        name="ColJustificado",
        fontName="Poppins-Regular",
        fontSize=9,
        leading=12,
        alignment=TA_JUSTIFY,
        spaceBefore=0,
        spaceAfter=0,
    )

    # Columnas
    ancho_columna = (ancho / 2) - 60  # deja 50px margen + 10px separación
    x_actual = 50
    x_reco = ancho / 2 + 10
    # Altura disponible para el texto (hasta  y - margen inferior)
    alto_disponible = y - 20  # 20pt margen inferior

    # Crear párrafos
    par_actual = Paragraph(actual, estilo_col)
    par_reco = Paragraph(recomendado, estilo_col)

    # Envolver y dibujar "Texto Actual"
    w_act, h_act = par_actual.wrap(ancho_columna, alto_disponible)
    par_actual.drawOn(c, x_actual, y - h_act - 5)  # 5pt debajo de la línea

    # Envolver y dibujar "Texto recomendado"
    w_rec, h_rec = par_reco.wrap(ancho_columna, alto_disponible)
    par_reco.drawOn(c, x_reco, y - h_rec - 5)

    return 145

def seccion_9(c, ancho, alto, y_inicio, datos_cv):
    # Colores
    azul_titulo   = HexColor("#028BBF")
    gris_cabecera = HexColor("#A9A9A9")
    gris_linea    = HexColor("#B0B0B0")
    green         = HexColor("#28A745")
    yellow        = HexColor("#FFC107")
    red           = HexColor("#DC3545")

    # Título
    c.setFont("Poppins-Bold", 14)
    c.setFillColor(azul_titulo)
    c.drawString(50, y_inicio, "Ajuste al puesto")

    # Div contenedor
    alto_rect = 300
    marg_h     = 20
    pad        = 20
    x_div      = marg_h + pad
    y_div      = y_inicio - alto_rect + pad
    ancho_div  = ancho - 2 * marg_h - 2 * pad
    alto_div   = alto_rect - 2 * pad

    c.setFillColor(colors.white)
    c.roundRect(x_div, y_div, ancho_div, alto_div, radius=15, fill=1, stroke=0)

    # Cabeceras
    y = y_div + alto_div - 20
    c.setFont("Poppins-SemiBold", 10)
    c.setFillColor(gris_cabecera)

    col1 = x_div + 10
    col2 = x_div + ancho_div * 0.2
    col3 = x_div + ancho_div * 0.5  # reducido de 0.6 a 0.5

    c.drawString(col1, y, "Área")
    ajuste_cabecera_estado = 50  # Ajusta este valor para mover más o menos
    c.drawString(col2 + ajuste_cabecera_estado, y, "Estado")

    c.drawString(col3, y, "Acción recomendada")

    c.setStrokeColor(gris_linea)
    c.setLineWidth(0.7)
    c.line(col1, y - 5, x_div + ancho_div - 10, y - 5)

    # Preparar datos
    ajuste = datos_cv.get('ajuste_puesto', {})
    mapping = {
        'habilidades_de_analisis':    'Herramientas de análisis',
        'resultados_cuantificables':  'Resultados cuantificables',
        'habilidades_blandas':        'Habilidades blandas',
        'lenguaje_tecnico':           'Lenguaje técnico',
    }
    data = []
    for clave, etiqueta in mapping.items():
        entry = ajuste.get(clave, {})
        nivel = entry.get('nivel', 'N/E')
        accion = entry.get('accion', '')
        color_estado = (
            green if nivel.lower() == 'alto' else
            yellow if nivel.lower() == 'medio' else
            red if nivel.lower() == 'bajo' else
            black
        )
        data.append((etiqueta, nivel, accion, color_estado))

    # Estilo justificado
    estilo_accion = ParagraphStyle(
        name="AccionJustificado",
        fontName="Poppins-Regular",
        fontSize=8,
        leading=10,
        alignment=TA_JUSTIFY,
        spaceBefore=0,
        spaceAfter=0,
    )

    # Dibujar filas
    c.setFont("Poppins-Regular", 9)
    y -= 25
    max_w_accion = x_div + ancho_div - col3 - 10  # ajustado al nuevo col3

    for i, (area, estado, accion, color_estado) in enumerate(data):
        # Área
        y_text = y
        c.setFillColor(black)
        for line in area.split('\n'):
            c.drawString(col1, y_text, line)
            y_text -= 12

        # Estado
        c.setFillColor(color_estado)
        x_circ = col2 + (ancho_div * 0.2 - 10) / 2
        c.circle(x_circ, y - 5, 5, fill=1, stroke=0)
        c.setFillColor(black)
        c.drawString(x_circ + 10, y - 10, estado)

        # Acción recomendada justificada
        par_acc = Paragraph(accion or "", estilo_accion)
        w_acc, h_acc = par_acc.wrap(max_w_accion, alto_div)
        par_acc.drawOn(c, col3, y - h_acc + 4)

        # Ajuste del siguiente y
        siguiente_y = min(y_text, y - h_acc) - 20
        if i < len(data) - 1:
            c.setStrokeColor(gris_linea)
            c.setLineWidth(0.5)
            c.line(col1, siguiente_y + 20, x_div + ancho_div - 10, siguiente_y + 20)
        y = siguiente_y

    return alto_rect -20

def seccion_10(c, ancho, alto, y_inicio, datos_cv):
    margen_horizontal = 30
    padding_interno = 20
    sombra_offset = 5
    desplazamiento_bajar_div = 30  # Baja el div blanco 30 pts

    # Datos de contenido
    experiencias = datos_cv.get('experiencia_laboral', [])

    # Estilo justificado para "Texto Recomendado"
    estilo_reco = ParagraphStyle(
        name="RecoJustificado",
        fontName="Poppins-Regular",
        fontSize=9,
        leading=11,
        alignment=TA_JUSTIFY,
        spaceBefore=0,
        spaceAfter=0,
    )

    # Estilo justificado para "Texto Actual"
    estilo_act = ParagraphStyle(
        name="ActJustificado",
        fontName="Poppins-Regular",
        fontSize=9,
        leading=11,
        alignment=TA_JUSTIFY,
        spaceBefore=0,
        spaceAfter=0,
    )

    # Cálculo dinámico del alto total basado en el contenido
    alto_rectangulo = 100  # Valor base para el rectángulo
    for exp in experiencias:
        # Empresa con wrap
        empresa = exp.get('Empresa', '')
        max_width_emp = ancho * 0.2 - 10
        lineas_empresa = wrap_text(empresa, max_width_emp, c, "Poppins-Regular", 9)
        
        # Texto Actual con wrap
        texto_actual = exp.get('Actual', '')
        max_width_act = ancho * 0.35 - 10
        lineas_actual = wrap_text(texto_actual, max_width_act, c, "Poppins-Regular", 9)
        
        # Texto Recomendado justificado via Paragraph
        texto_recomendado = exp.get('Recomendado', '')
        ancho_reco = ancho * 0.4 - 10
        par_reco = Paragraph(texto_recomendado, estilo_reco)
        w_reco, h_reco = par_reco.wrap(ancho_reco, alto)
        
        # Ajustar el alto total del rectángulo según el contenido
        alto_rectangulo += max(len(lineas_empresa), len(lineas_actual), int(h_reco / 12)) * 12 + 40  # Agregamos 20 por espaciado entre filas

    # Definición del alto del fondo degradado
    alto_degradado = alto_rectangulo - 60  # Añadir un margen adicional para el fondo

    # Fondo degradado
    imagen_fondo = ImageReader('./public/img/fondo.png')
    c.drawImage(imagen_fondo, 0, y_inicio - alto_degradado, width=ancho, height=alto_degradado)

    # Título
    c.setFont("Poppins-Bold", 18)
    c.setFillColor(colors.white)
    titulo = "Experiencia Laboral"
    ancho_titulo = c.stringWidth(titulo, "Poppins-Bold", 18)
    x_titulo = margen_horizontal + (ancho - 2 * margen_horizontal - ancho_titulo) / 2
    y_titulo = y_inicio - 40
    c.drawString(x_titulo, y_titulo, titulo)

    # Div blanco con sombra
    y_div = y_inicio - alto_rectangulo + 20 + padding_interno - desplazamiento_bajar_div - 20
    x_div = margen_horizontal + padding_interno
    ancho_div = ancho - 2 * margen_horizontal - 2 * padding_interno
    alto_div = alto_rectangulo - 20 - 2 * padding_interno

    # Sombra
    c.setFillColorRGB(0, 0, 0, alpha=0.15)
    c.roundRect(x_div + sombra_offset, y_div - sombra_offset, ancho_div, alto_div, radius=15, fill=1, stroke=0)
    # Div blanco
    c.setFillColor(colors.white)
    c.roundRect(x_div, y_div, ancho_div, alto_div, radius=15, fill=1, stroke=0)

    # Cabeceras
    padding_top_div = 20
    y = y_div + alto_div - padding_top_div
    c.setFont("Poppins-SemiBold", 10)
    c.setFillColor(HexColor("#A9A9A9"))
    margen_col1 = x_div + 10
    margen_col2 = x_div + ancho_div * 0.2
    margen_col3 = x_div + ancho_div * 0.6
    c.drawString(margen_col1, y, "Empresa")
    c.drawString(margen_col2, y, "Texto Actual")
    c.drawString(margen_col3, y, "Texto Recomendado")

    gris_linea = HexColor("#B0B0B0")
    c.setStrokeColor(gris_linea)
    c.setLineWidth(0.7)
    c.line(margen_col1, y - 5, x_div + ancho_div - 10, y - 5)

    # Cuerpo de la tabla
    c.setFont("Poppins-Regular", 9)
    y -= 25

    for i, exp in enumerate(experiencias):
        empresa = exp.get('Empresa', '')
        texto_actual = exp.get('Actual', '')
        texto_recomendado = exp.get('Recomendado', '')

        # Empresa con wrap
        max_width_emp = ancho_div * 0.2 - 10
        lineas_empresa = wrap_text(empresa, max_width_emp, c, "Poppins-Regular", 9)
        y_emp = y
        c.setFillColor(colors.black)
        for linea in lineas_empresa:
            c.drawString(margen_col1, y_emp, linea)
            y_emp -= 12

        # Texto Actual con justificación via Paragraph
        ancho_act = ancho_div * 0.35 - 10
        par_act = Paragraph(texto_actual, estilo_act)
        w_act, h_act = par_act.wrap(ancho_act, alto_div)
        y_act_start = y + 15
        par_act.drawOn(c, margen_col2, y_act_start - h_act)

        # Texto Recomendado justificado via Paragraph
        ancho_reco = ancho_div * 0.4 - 10
        par_reco = Paragraph(texto_recomendado, estilo_reco)
        w_reco, h_reco = par_reco.wrap(ancho_reco, alto_div)
        y_reco_start = y + 15
        par_reco.drawOn(c, margen_col3, y_reco_start - h_reco)

        # Ajustar y para siguiente fila
        siguiente_y = min(y_emp, y_act_start - h_act, y_reco_start - h_reco) - 20

        # Línea separadora
        if i < len(experiencias) - 1:
            c.setStrokeColor(gris_linea)
            c.setLineWidth(0.5)
            c.line(margen_col1, siguiente_y + 20, x_div + ancho_div - 10, siguiente_y + 20)

        y = siguiente_y

    altura_ocupada = alto_rectangulo + desplazamiento_bajar_div + 20
    return altura_ocupada

def seccion_11(c, ancho, alto, y_inicio, datos_cv):
    margen_izq = 50
    margen_der = 100          # Aumento del margen derecho
    espacio_columna = 20      # Separación extra entre bloques
    y = y_inicio
    azul_titulo = HexColor("#028BBF")

    # Estilo justificado para columnas de Voluntariado/Educación
    estilo_just = ParagraphStyle(
        name="Justificado",
        fontName="Poppins-Regular",
        fontSize=9,
        leading=11,
        alignment=TA_JUSTIFY,
        spaceBefore=0,
        spaceAfter=0,
    )

    # -------------------------------------------------------------------
    # Habilidades y Herramientas (Columna 1)
    # -------------------------------------------------------------------
    c.setFont("Poppins-Bold", 14)
    c.setFillColor(azul_titulo)
    c.drawString(margen_izq, y, "Habilidades y")
    c.drawString(margen_izq, y - 16, "Herramientas")

    # Ajuste para comenzar la lista de habilidades y herramientas
    y_hh = y - 40
    c.setFont("Poppins-Bold", 9)
    c.setFillColor(black)
    c.drawString(margen_izq, y_hh, "Organízalas así:")

    c.setFont("Poppins-Regular", 9)
    habilidades = datos_cv.get('habilidades_herramientas', [])
    max_width_hh = ancho - margen_izq - margen_der  # Usamos todo el ancho disponible
    y_hh -= 20
    for habilidad in habilidades:
        lineas = wrap_text(habilidad, max_width_hh, c, "Poppins-Regular", 8)
        for linea in lineas:
            c.drawString(margen_izq, y_hh, linea)
            y_hh -= 12
        y_hh -= 15  # espacio entre ítems

    # -------------------------------------------------------------------
    # Separación entre Habilidades y Herramientas y Educación (en la misma fila)
    # -------------------------------------------------------------------
    y_hh -= 30  # Espacio entre secciones para no sobreponerse
    c.setFont("Poppins-Bold", 14)
    c.setFillColor(azul_titulo)
    c.drawString(margen_izq, y_hh, "Educación")

    # Ajuste para Educación
    y_educ = y_hh - 40
    c.setFont("Poppins-Bold", 9)
    c.setFillColor(black)
    c.drawString(margen_izq, y_educ, "Incluye tus estudios y proyectos destacados:")
    
    c.setFont("Poppins-Regular", 9)
    estudios = datos_cv.get('educacion', [])
    max_width_edu = ancho - margen_izq - margen_der  # Usamos todo el ancho disponible
    y_educ -= 20
    for punto in estudios:
        lineas = wrap_text(punto, max_width_edu, c, "Poppins-Regular", 8)
        for linea in lineas:
            c.drawString(margen_izq, y_educ, linea)
            y_educ -= 12
        y_educ -= 15

    # -------------------------------------------------------------------
    # Voluntariado
    # -------------------------------------------------------------------
    c.setFont("Poppins-Bold", 14)
    c.setFillColor(azul_titulo)

    # Agregar más separación antes de la sección de Voluntariado
    y_vol = y_educ - 50  # He aumentado la separación de 30 a 50
    c.drawString(margen_izq, y_vol, "Voluntariado")

    y_vol -= 40  # Ajuste adicional para que la parte de "Voluntariado" no se solape
    c.setFont("Poppins-SemiBold", 10)
    c.setFillColor(black)
    c.drawString(margen_izq, y_vol, "Organización")
    c.drawString(margen_izq + 100, y_vol, "Texto Actual")
    c.drawString(margen_izq + 300, y_vol, "Texto Recomendado")

    y_vol -= 20
    c.setStrokeColor(colors.HexColor("#B0B0B0"))
    c.setLineWidth(0.7)
    c.line(margen_izq, y_vol, ancho - margen_der, y_vol)
    y_vol -= 20

    voluntariado = datos_cv.get('voluntariado', [])
    for item in voluntariado:
        org = item.get("Organización", "No disponible") or "No disponible"
        actual = item.get("Actual", "No disponible") or "No disponible"
        reco = item.get("Recomendado", "No disponible") or "No disponible"

        # Organización
        y_org = y_vol
        for linea in wrap_text(org, 90, c, "Poppins-Regular", 9):
            c.drawString(margen_izq, y_org, linea)
            y_org -= 12

        # Texto Actual
        par_act = Paragraph(actual, estilo_just)
        ancho_act = 180
        w_act, h_act = par_act.wrap(ancho_act, alto)
        par_act.drawOn(c, margen_izq + 100, y_vol - h_act + 5)

        # Texto Recomendado
        par_reco = Paragraph(reco, estilo_just)
        ancho_reco = ancho - (margen_izq + 300) - margen_der
        w_rec, h_rec = par_reco.wrap(ancho_reco, alto)
        par_reco.drawOn(c, margen_izq + 300, y_vol - h_rec + 5)

        # Ajuste de la altura (alineación de las sugerencias)
        max_h = max(h_act, h_rec)
        y_vol = y_vol - max_h - 20  # Ajustamos la altura de la siguiente línea
        if item is not voluntariado[-1]:
            c.setStrokeColor(colors.HexColor("#B0B0B0"))
            c.setLineWidth(0.5)
            c.line(margen_izq, y_vol + 15, ancho - margen_der, y_vol + 15)

    altura_ocupada = y_inicio - y_vol
    return altura_ocupada - 20

# SECCION 12 - JUSTIFICADO
def seccion_12(c, ancho, alto, y_inicio, datos_cv):
    # Alturas y márgenes
    alto_degradado    = 250
    alto_rectangulo   = 300
    margen_horizontal = 30
    padding_interno   = 20
    sombra_offset     = 5
    bajar_div         = 30

    # Fondo degradado
    imagen_fondo = ImageReader('./public/img/fondo2.png')
    c.drawImage(imagen_fondo, 0, y_inicio - alto_degradado,
                width=ancho, height=alto_degradado)

    # Título encima del degradado
    titulo = "Formato y optimización"
    c.setFont("Poppins-Bold", 18)
    c.setFillColor(white)
    ancho_tit = c.stringWidth(titulo, "Poppins-Bold", 18)
    x_tit = margen_horizontal + (ancho - 2*margen_horizontal - ancho_tit)/2
    c.drawString(x_tit, y_inicio - 40, titulo)

    # Coordenadas del div blanco
    y_div     = y_inicio - alto_rectangulo + padding_interno - bajar_div
    x_div     = margen_horizontal + padding_interno
    ancho_div = ancho - 2*margen_horizontal - 2*padding_interno
    alto_div  = alto_rectangulo - 2*padding_interno - 20

    # Sombra y fondo blanco
    c.setFillColorRGB(0,0,0, alpha=0.15)
    c.roundRect(x_div + sombra_offset, y_div - sombra_offset,
                ancho_div, alto_div, radius=15, fill=1, stroke=0)
    c.setFillColor(white)
    c.roundRect(x_div, y_div, ancho_div, alto_div,
                radius=15, fill=1, stroke=0)

    # Cabeceras
    padding_top = 20
    margen_int  = 10
    y = y_div + alto_div - padding_top

    c.setFont("Poppins-SemiBold", 10)
    c.setFillColor(HexColor("#A9A9A9"))

    col1 = x_div + margen_int
    col2 = x_div + ancho_div * 0.2 + margen_int
    # Ahora col3 al 48% para acercar más
    col3 = x_div + ancho_div * 0.48 + margen_int

    # Centrar "Estado"
    cabe_est = "Estado"
    w_est = c.stringWidth(cabe_est, "Poppins-SemiBold", 10)
    x_est = col2 + (ancho_div * 0.2 - w_est)/2

    c.drawString(col1, y, "Elemento")
    c.drawString(x_est, y, cabe_est)
    c.drawString(col3, y, "Sugerencia")

    gris = HexColor("#B0B0B0")
    c.setStrokeColor(gris)
    c.setLineWidth(0.7)
    c.line(col1, y-5, x_div + ancho_div - margen_int, y-5)

    # Estilo justificado para "Sugerencia"
    estilo_sug = ParagraphStyle(
        name="SugJustificado",
        fontName="Poppins-Regular",
        fontSize=8,
        leading=10,
        alignment=TA_JUSTIFY,
        spaceBefore=0,
        spaceAfter=0,
    )

    # Datos dinámicos
    ajuste = datos_cv.get('formato-optimizacion', {})
    mapping = {
        'longitud':          'Longitud',
        'foto':              'Foto',
        'palabras_clave':    'Palabras clave',
        'verbos_de_impacto': 'Verbos de impacto',
    }
    green  = HexColor("#28A745")
    yellow = HexColor("#FFC107")
    red    = HexColor("#DC3545")

    data = []
    for key, label in mapping.items():
        ent = ajuste.get(key, {})
        estado     = ent.get('estado', 'N/E')
        sugerencia = ent.get('sugerencia', '')
        nivel = estado.lower()
        if nivel == 'alto':
            color = green
        elif nivel == 'medio':
            color = yellow
        elif nivel == 'bajo':
            color = red
        else:
            color = black
        data.append((label, estado, sugerencia, color))

    # Dibujar filas
    c.setFont("Poppins-Regular", 9)
    y -= 25
    # max_w_sug es el espacio restante tras col3
    max_w_sug = x_div + ancho_div - col3 - margen_int

    for i, (elem, est, sug, col) in enumerate(data):
        # Elemento
        y_text = y
        for ln in elem.split('\n'):
            c.setFillColor(black)
            c.drawString(col1, y_text, ln)
            y_text -= 12

        # Círculo y texto de estado
        c.setFillColor(col)
        x_c = col2 + (ancho_div * 0.2 - 10)/2
        c.circle(x_c, y - 5, 5, fill=1, stroke=0)
        c.setFillColor(black)
        c.drawString(x_c + 10, y - 10, est)

        # Sugerencia justificada
        par_sug = Paragraph(sug or "", estilo_sug)
        w_sug, h_sug = par_sug.wrap(max_w_sug, alto_div)
        par_sug.drawOn(c, col3, y - h_sug + 4)

        # Preparar y de la siguiente fila
        y = min(y_text, y - h_sug) - 20
        if i < len(data) - 1:
            c.setStrokeColor(gris)
            c.setLineWidth(0.5)
            c.line(col1, y + 20, x_div + ancho_div - margen_int, y + 20)

    return alto_rectangulo +20

def seccion_13(c, ancho, alto, y_inicio, logo_path): 
    # Calcular las dimensiones de la imagen
    imagen = ImageReader(logo_path)
    imagen_width = 120  # Puedes ajustar el tamaño de la imagen según sea necesario
    imagen_height = 26  # Ajusta la altura de la imagen también

    # Calcular la posición centrada para la imagen
    x_imagen = (ancho - imagen_width) / 2
    y_imagen = y_inicio - imagen_height - 20  # Ajustar un poco hacia abajo

    # Dibujar la imagen centrada en la sección
    c.drawImage(imagen, x_imagen, y_imagen, width=imagen_width, height=imagen_height, mask='auto')

    # Definir la altura ocupada en la sección
    altura_ocupada = imagen_height - 10  # Incluir el espacio para la imagen y un poco de margen

    return altura_ocupada -20
   
# Ruta donde se guardarán los PDFs generados
CARPETA_PDFS = "static/analisis_pdfs/"

# Verificar si la carpeta existe, si no, crearla
if not os.path.exists(CARPETA_PDFS):
    os.makedirs(CARPETA_PDFS)

def generar_pdf_con_secciones(datos_cv, nombre_archivo, logo_path, ruta_logo2):
    ancho = 8.5 * inch
    alto = 52 * inch  # Tamaño carta

    c = canvas.Canvas(CARPETA_PDFS + nombre_archivo, pagesize=(ancho, alto))  # Guardar en la ruta especificada

    # Encabezado con la información básica
    seccion_encabezado(c, ancho, alto, logo_path)
    y_actual = alto - 80  # Ajusta la posición según necesites

    y_actual = alto - 40  
    espacio_entre_secciones = 20

    altura = seccion_2(c, ancho, alto, y_actual, datos_cv)
    y_actual -= altura + espacio_entre_secciones

    altura = seccion_3(c, ancho, alto, y_actual, datos_cv)
    y_actual -= altura + espacio_entre_secciones

    altura = seccion_4(c, ancho, alto, y_actual, datos_cv)
    y_actual -= altura + espacio_entre_secciones

    altura = seccion_5(c, ancho, alto, y_actual, datos_cv)
    y_actual -= altura + espacio_entre_secciones

    altura = seccion_6(c, ancho, alto, y_actual,datos_cv)
    y_actual -= altura + espacio_entre_secciones

    altura = seccion_7(c, ancho, alto, y_actual,datos_cv)
    y_actual -= altura + espacio_entre_secciones

    altura = seccion_8(c, ancho, alto, y_actual, datos_cv)
    y_actual -= altura + espacio_entre_secciones
    
    altura = seccion_9(c, ancho, alto, y_actual, datos_cv)
    y_actual -= altura + espacio_entre_secciones
    
    altura = seccion_10(c, ancho, alto, y_actual, datos_cv)
    y_actual -= altura + espacio_entre_secciones

    altura = seccion_11(c, ancho, alto, y_actual, datos_cv)
    y_actual -= altura + espacio_entre_secciones


    altura = seccion_12(c, ancho, alto, y_actual,datos_cv)
    y_actual -= altura + espacio_entre_secciones


    altura = seccion_13(c, ancho, alto, y_actual, logo_path)
    y_actual -= altura + espacio_entre_secciones

    # Guardar el PDF
    c.save()
    return f"/static/analisis_pdfs/{nombre_archivo}"  # Guarda el PDF en la carpeta estática