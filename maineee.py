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
import zipfile
import io
import json
import re

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

@app.get("/analizar-cv/")
async def analizar_cv(pdf_url: str, file_original: str, puesto_postular: str):
    
    response = requests.get(pdf_url)
    
    puesto = puesto_postular

    if response.status_code != 200:
        return {"error": "No se pudo descargar el archivo PDF."}
    
    pdf_content = BytesIO(response.content)

    contenido, num_paginas = extract_text_from_pdf(pdf_content)

    #  return JSONResponse(contenido)


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
    - `"paginas"`: el número total de páginas del CV (ya proporcionado).
    - `"comentario"`: la evaluación clara y profesional, iniciando con una de las frases mencionadas y luego desarrollando una recomendación breve pero experta.

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
    "comentario": comentario correspondiente según cantidad de errores,
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

    #filename = obtener_nombre_archivo_desde_url(pdf_url)
   
    filename = file_original
    print("FILENAME",file_original)
    filename_json = json.dumps(filename)
    contenido_json = json.dumps(contenido)

    prompt4 = f"""Eres un experto en marca personal y empleabilidad. Tu tarea es analizar el nombre del archivo de un currículum (CV) para determinar si es profesional.

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
    "comentario": "Dime si es adecuado o no, por qué, y sugiere un nombre más profesional si aplica."
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

    Responde en formato JSON con:

    - "evaluacion": una lista de objetos, uno por cada elemento, con las siguientes claves:
    - "elemento": el nombre del campo evaluado
    - "existe": true o false
    - "bien_posicionado": true o false
    - "facil_de_distinguir": true o false

    - "comentario_general": una conclusión clara y profesional de mínimo 25 palabras sobre la presentación general de estos elementos. Evalúa si son suficientes, si están bien organizados o si requieren mejoras para facilitar la lectura y comprensión del CV.

    No añadas ningún texto fuera del JSON.

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

    🔍 **Ignora las siguientes categorías de palabras**:
    - Artículos: el, la, los, las, un, una, unos, unas
    - Preposiciones: de, en, con, por, para, sobre, entre, hasta, hacia, desde
    - Conjunciones y conectores: y, o, u, pero, aunque, sino, mientras, así, entonces
    - Pronombres comunes: yo, tú, él, ella, nosotros, ustedes, ellos
    - Verbos muy comunes: ser, estar, haber, tener, hacer (solo si no están en exceso)
    - Monosílabos vacíos de contenido: a, e, es, al, lo, sí, no, se, que, qué, ya, más
    - Palabras similares con diferencia de género o número (ej: "capacidad" y "capacidades" se cuentan como una sola)

    📤 Devuelve **solo** un JSON con esta estructura:

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

    Habla de tú a tú, como si dieras una recomendación directa al candidato. Usa un **solo párrafo**, en tono natural (sin parecer una IA ni usar lenguaje técnico innecesario).

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

    - "nivel": un número entero del 1 al 10, donde 10 representa un uso excelente de verbos de impacto.
    - "comentario": una observación profesional breve y clara, de aproximadamente 160 caracteres (no más de 180). Usa un estilo formal, sin emojis.
    - "sugerencias": una lista de 3 sugerencias específicas para mejorar los verbos en la redacción del CV. Cada sugerencia debe tener al menos 20 palabras y explicar claramente cómo mejorar un verbo genérico o repetido, incluyendo un ejemplo concreto de reemplazo.

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

    Tu objetivo es evaluar la redacción del texto actual y sugerir una versión mejorada que sea más clara, profesional y alineada con estándares actuales. Mantén un tono formal, positivo y directo.

    Devuelve solo un JSON con esta estructura:

    {{
    "actual": "Texto actual del primer párrafo, sin encabezados ni contactos.",
    "recomendado": "Texto recomendado, redactado de forma más clara y profesional."
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
    2. Una acción concreta para mejorar: debe ser breve, práctica y de aplicación inmediata. Si es posible, sugiere reemplazos específicos en el formato: “cambiar #X# por #Y#”.

    Formato de salida JSON con claves en snake_case. No añadas explicaciones ni texto adicional fuera del JSON.

    Contenido del CV:
    \"\"\"{contenido}\"\"\"
    """

    response10 = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt10}],
        temperature=0.7,
        #max_tokens=50  
    )
    ajuste_puesto = response10['choices'][0]['message']['content']
    try:
        ajuste_puesto_json = clean_and_load_json(ajuste_puesto)
    except json.JSONDecodeError as e:
        print("Error al decodificar JSON:", e)
        ajuste_puesto_json = None
    print(ajuste_puesto_json)


    prompt11 = f"""
    Brinda sugerencias personalizadas de mejora por sección del CV, orientadas al rol de {puesto}.

    En esta parte, cubre lo siguiente:

    - En "Empresa" indica el nombre de la empresa tal como aparece en el CV.
    - En "Actual" incluye el texto completo de la experiencia laboral tal como figura en el CV.
    - En "Recomendado" proporciona una versión mejorada del texto de experiencia laboral, aplicando lo siguiente:
        - Iniciar con un verbo de acción fuerte.
        - Incluir resultados cuantificables si aplica.
        - Alinear con las funciones o competencias clave para el rol de {puesto}.
        - Usa el contenido original como base y mejóralo directamente. No inventes logros no mencionados.
        - Mantén el mismo contenido, solo mejora redacción, impacto y claridad.

    Devuélveme solo un JSON con el siguiente formato:

    [
    {{
        "Empresa": "Nombre de la empresa",
        "Actual": "Texto original tal como aparece en el CV.",
        "Recomendado": "Texto mejorado aplicando verbos de impacto, claridad y orientación al puesto de {puesto}."
    }},
    {{
        "Empresa": "Nombre de la empresa",
        "Actual": "Texto original tal como aparece en el CV.",
        "Recomendado": "Texto mejorado aplicando verbos de impacto, claridad y orientación al puesto de {puesto}."
    }}
    ]

        Solo analiza la sección de experiencia laboral.
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
    - Señalar aspectos como: agregar fechas si faltan, detallar el grado obtenido, evitar abreviaciones poco claras, incluir logros destacados si los hay, o mejorar la alineación con el perfil requerido para el puesto de {puesto}.
    - Cada recomendación debe tener al menos 20 palabras.
    - No inventes información no presente en el CV.
    - Si no hay una sección de educación/formación académica en el CV, incluye una única recomendación indicando que dicha sección no fue encontrada.

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
    Actúa como un experto en revisión profesional de currículums (CVs), con énfasis en formato, claridad y atracción para reclutadores.

    Evalúa el siguiente contenido extraído de un CV:

    \"\"\"{contenido}\"\"\"

    El rol objetivo es: **{puesto}**

    Tu tarea es analizar el formato del CV con base en los siguientes criterios, orientados a mejorar su presentación y efectividad:

    1. **Longitud**: Evalúa si el CV excede 1 página (en perfiles junior o intermedios) o si es innecesariamente largo para el rol. el num de paginas es {num_paginas} . recuerda que un CV debe ser conciso y fácil de leer. si es 1 hoja el estado es "Alto", si es 2 hojas "Medio" y si es más de 2 "Bajo".

    2. **Foto**: Verifica si el CV incluye una foto. La mayoría de los filtros automáticos de RRHH no lo recomiendan, especialmente en países donde se evita por sesgos. ENtonces, si hay foto el estado es "Bajo", si no hay foto el estado es "Alto". 
    
    3. **Palabras clave**: Evalúa si incluye términos relevantes al puesto, como tecnologías, habilidades técnicas, o conceptos específicos (por ejemplo, en el caso de {puesto}, busca términos como: análisis de riesgo, scoring, producto financiero, gestión, liderazgo, procesos, herramientas, etc.).
    4. **Verbos de impacto**: Evalúa si se utilizan verbos potentes y orientados a resultados, como: "lideré", "implementé", "optimizé", "logré", en lugar de verbos vagos o pasivos como "encargado de", "apoyé", "participé".

    Para cada uno de estos 4 criterios, responde con:

    - `"estado"`: Puede ser **"Alto"**, **"Medio"** o **"Bajo"**, según la calidad o presencia del elemento.
    - `"sugerencia"`: Breve texto con una recomendación concreta para mejorar o justificar la evaluación.

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

    return JSONResponse(content={
        # 1 Analisis Principal
        "mainly_analysis": json.loads(mainly_analysis),
        # 2 Tamaño del CV
        "pagination": json.loads(pagination),
        # 3 Ortografía
        "spelling": json.loads(spelling),
        # 4 Nombre del archivo
        "filename": json.loads(filename_response),
        # 5 Indispensables
        "indispensable": json.loads(indispensable),
        # 6 Palabras repetidas
        "repeat_words": json.loads(repeat_words),
        # 7 Relevancia de la experiencia
        "relevance": relevance,
        # 8 Verbos de impacto
        "verbos_impact": json.loads(verbos_impact),
        # 9 Perfil Profesional
        "perfil_profesional": json.loads(perfil_profesional),
        # 10 Ajuste al puesto
        "ajuste_puesto": ajuste_puesto_json,
        # 11 Experiencia laboral
        "experiencia_laboral": json.loads(experiencia_laboral),
        # 12 Habilidades y Herramientas
        "habilidades_herramientas": json.loads(habilidades_herramientas)['recomendaciones'],
        # 13 Educación
        "educacion": json.loads(educacion),
        # 14 Voluntariado
        "voluntariado": voluntariado_json,
        # 15 Formato y Optimización del CV
        "formato-optimizacion": json.loads(formato_optimizacion)
    })