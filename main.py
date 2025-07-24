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
from fastapi.middleware.cors import CORSMiddleware       
from pydantic import BaseModel


pdfmetrics.registerFont(TTFont('Poppins-Regular', './fonts/Poppins-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Poppins-Bold', './fonts/Poppins-Bold.ttf'))
pdfmetrics.registerFont(TTFont('Poppins-SemiBold', './fonts/Poppins-SemiBold.ttf'))
pdfmetrics.registerFont(TTFont('Poppins-Italic', './fonts/Poppins-Italic.ttf'))

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # permite todos los dominios
    allow_credentials=True,
    allow_methods=["*"],       # GET, POST, PUT, DELETE, OPTIONS...
    allow_headers=["*"],       # cualquier cabecera
)

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

def es_json_valido(texto):
    try:
        # Intentamos cargar el texto como JSON
        json.loads(texto)
        return True
    except json.JSONDecodeError:
        return False

        
@app.get("/backup-static/")
async def backup_static():
    static_folder = "static"
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(static_folder):
            for file in files:
                file_path = os.path.join(root, file)
                # Añadir archivo al zip con ruta relativa
                arcname = os.path.relpath(file_path, static_folder)
                zip_file.write(file_path, arcname=arcname)

    zip_buffer.seek(0)
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=static_backup.zip"})


class CVRequest(BaseModel):
    pdf_url: str
    puesto_postular: str
    original_name: str
    descripcion_puesto: str

@app.post("/analizar-cv/")
async def analizar_cv(request: CVRequest):
    start_time = time.time()
    end_time = time.time()
    processing_time_ms = int((end_time - start_time) * 1000)  # Convertir a milisegundos
    analysis_datetime = datetime.now().isoformat()  # "YYYY-MM-DDTHH:MM:SS"
    
    pdf_url = request.pdf_url
    puesto_postular = request.puesto_postular
    original_name = request.original_name
    descripcion_puesto = request.descripcion_puesto

    original_pdf = pdf_url

    response = requests.get(pdf_url)

    
    puesto = puesto_postular

    if response.status_code != 200:
        return {"error": "No se pudo descargar el archivo PDF."}
    
    pdf_content = BytesIO(response.content)

    contenido, num_paginas = extract_text_from_pdf(pdf_content)

   # email = extract_email(contenido)

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

    response0 = openai.Completion.create(
        model="gpt-3.5-turbo-instruct",  
        prompt=prompt0,  
        temperature=0.7,
    )
    print("Respuesta de OpenAI:", response0['choices'][0]['text'])
    candidate_name = response0['choices'][0]['text']  



    prompt1 = f"""
    Eres un reclutador profesional. Recibirás el perfil de un candidato en formato JSON y deberás evaluar su idoneidad para el puesto de "{puesto}" teniendo en cuenta tambien que el puesto consiste en "{descripcion_puesto}" .

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

    No incluyas ningún otro texto fuera del JSON. Tienes que darme un JSON perfecto

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
    )
    
    spelling = response3['choices'][0]['message']['content']



    filename = original_name
    print("FILENAME",original_name)
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
    )
    filename_response = response4['choices'][0]['message']['content']


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
        "comentario_general": "Comentario personalizado en tercera persona, con un maximo 40 palabras. Usa frases como 'El CV', 'se recomienda', 'se considera'."
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
    Actúa como un experto en redacción de currículums. Analiza el contenido que te doy.


    Tu objetivo es evaluar la redacción del texto actual y sugerir una versión mejorada que sea más clara, profesional y alineada con estándares actuales. Usa como guía el siguiente enfoque de redacción (no lo copies literalmente):

    Debe empezar con: "Estudiante de “Número” ciclo de “Carrera” en la/el “Nombre de la Universidad”". Haz lo posible por ecnontrar esa informacion, en todo el texto. En caso no encuentres la informacino necesesaria indica algo como Estudiante de 'X' de la carrera 'Y' de la Universidad 'Z' como recomendacion. A partir de ahí, describe la identidad profesional de forma integral, combinando elementos personales como mentalidad, valores o trayectoria con intereses profesionales, fortalezas, experiencias relevantes o áreas de especialización. El objetivo es proyectar una imagen clara, auténtica y alineada con las metas profesionales del estudiante. Añade un toque personal que haga sentir al lector que conoce al candidato, pero manteniendo un tono profesional y directo. de acuerdo al puesto de {puesto} teniendo en cuenta tambien que el puesto consiste en "{descripcion_puesto}". en lo posible identifica la carrera y la universidad del candidato.

    No menciones para nada "X" "Y" "Z" no los menciones, tienes que si o si de todo el {contenido} encontrar la carrera, universidad.
    Devuelve solo un JSON con esta estructura:

    {{
    "actual": "Texto actual del primer párrafo, sin encabezados ni contactos. Maximo unas 30 palabras",
    "recomendado": "Texto recomendado, redactado de forma más clara y profesional, alineado con el enfoque sugerido. Maximo 40 palabras"
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
    Actúa como un reclutador experto en selección de personal para el rol de {puesto} teniendo en cuenta tambien que el puesto consiste en "{descripcion_puesto}". Evalúa el contenido del siguiente CV y clasifícalo en las siguientes categorías:

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

    def safe_json_load(data):
        try:
            # Intentamos cargar el JSON
            return json.loads(data)
        except json.JSONDecodeError:
            # Si ocurre un error, retornamos None o el valor que prefieras
            return None

    def process_ats_response(response):
        ats_data = safe_json_load(response)

        if ats_data is None or "atsCompliance" not in ats_data:
            ats_data = {
                "atsCompliance": {
                    "score": 0,
                    "issues": [],
                    "recommendations": []
                }
            }

        ats_data["atsCompliance"].setdefault("score", 0)
        ats_data["atsCompliance"].setdefault("issues", [])
        ats_data["atsCompliance"].setdefault("recommendations", [])

        return ats_data

    response10 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt10}],
        temperature=0.7,
    )
    ajuste_puesto = response10['choices'][0]['message']['content']


    prompt_ats_compliance = f"""
    Eres un reclutador profesional con experiencia en el uso de sistemas de seguimiento de candidatos (ATS). A continuación, se muestra el contenido del CV de un candidato para el puesto de {puesto} teniendo en cuenta tambien que el puesto consiste en "{descripcion_puesto}". 
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

    prompt_keywords = f"""
    Eres un reclutador profesional. A continuación, se muestra el contenido del CV de un candidato para el puesto de {puesto} teniendo en cuenta tambien que el puesto consiste en "{descripcion_puesto}". 
    Por favor, extrae las palabras clave relevantes para el puesto en cuestión y las habilidades generales mencionadas en el CV. 

    Primero, identifica las palabras clave relacionadas con el puesto de {puesto} teniendo en cuenta tambien que el puesto consiste en "{descripcion_puesto}", estas pueden ser habilidades técnicas, habilidades blandas o certificaciones que son relevantes para el rol. Luego, clasifica las palabras clave en las siguientes categorías:

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


    prompt_feedback_summary = f"""
    Eres un reclutador profesional. A continuación, se muestra el contenido del CV de un candidato para el puesto de {puesto} teniendo en cuenta tambien que el puesto consiste en "{descripcion_puesto}". Por favor, proporciona un resumen general del feedback para el candidato, considerando los siguientes aspectos:

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


    resultados = {
        "nombre": json.loads(candidate_name),
        "mainly_analysis": clean_and_load_json(mainly_analysis),
        "spelling": clean_and_load_json(spelling),
        "filename": clean_and_load_json(filename_response),
        "indispensable": clean_and_load_json(indispensable),
        "repeat_words": clean_and_load_json(repeat_words),
        "relevance": relevance,
        "verbos_impact": clean_and_load_json(verbos_impact),
        "perfil_profesional": clean_and_load_json(perfil_profesional),
        "ajuste_puesto": clean_and_load_json(ajuste_puesto),
        "puesto_postular": puesto,
        "extractedData": {
            "analysisResults": { 
                "atsCompliance": ats_compliance["atsCompliance"],
                "keywordAnalysis": keywords["keywordAnalysis"],
                "feedbackSummary": feedback_summary  # Aquí agregamos el feedback summary

            }
        },

    }

    # Generar el PDF y obtener la ruta
    #ruta_pdf = generar_pdf_con_secciones(resultados, nombre_pdf, ruta_logo,ruta_logo2)  # Aquí pasamos la ruta del logo

    # Agregar la ruta del PDF al JSON de la respuesta
    #resultados["pdf_evaluado"] = ruta_pdf

    return JSONResponse(content=resultados)

   