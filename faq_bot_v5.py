import json
import random
import unicodedata
import re

from pathlib import Path

def cargar_faqs(nombre_archivo="faqs.json"):
    """
    Carga las FAQs desde un archivo JSON.
    """
    ruta_base = Path(__file__).resolve().parent
    ruta_json = ruta_base / nombre_archivo

    with open(ruta_json, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def quitar_tildes(texto):
    """
    Elimina tildes y acentos.
    """
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def normalizar_texto(texto):
    """
    Convierte el texto a minúsculas, quita tildes y espacios sobrantes.
    """
    texto = texto.lower().strip()
    texto = quitar_tildes(texto)
    return texto

def normalizar_texto_extendido(texto):
    texto = normalizar_texto(texto)

    reemplazos = {
    " q ": " que ",
    " x ": " por ",
    " toy ": "estoy",
    " aki toy ":"aqui estoy",
    " xa ": " para ",
    " pa ": " para ",
    " pq ": " porque ",
    " xq ": " porque ",
    " porq ": " porque ",
    " tmb ": " también ",
    " tb ": " también ",
    " tmp ": " tampoco / tiempo, según contexto ",
    " d ": " de ",
    " dl ": " del ",
    " alq ": " algo ",
    " algn ": " algún ",
    " algna ": " alguna ",
    " algns ": " algunos ",
    " algnas ": " algunas ",
    " ns ": " no sé ",
    " npi ": " ni idea ",
    " ntp ": " no te preocupes ",
    " tranqui ": " tranquilo / tranquila ",
    " finde ": " fin de semana ",
    " msj ": " mensaje ",
    " priv ": " privado ",
    " insta ": " Instagram ",
    " tlf ": " teléfono ",
    " num ": " número ",
    " nrml ": " normal ",
    " bn ": " bien ",
    " bno ": " bueno ",
    " weno ": " bueno ",
    " ola ": " hola ",
    " adio ": " adiós ",
    " toi ": " estoy ",
    " tas ": " estás ",
    " tamos ": " estamos ",
    " to ": " todo ",
    " toa ": " toda ",
    " tos ": " todos ",
    " tas bien? ": " ¿estás bien? ",
    " qtal ": " qué tal ",
    " q tl ": " qué tal ",
    " cm ": " como ",
    " cmo ": " como ",
    " dd ": " donde ",
    " dnd ": " donde ",
    " mñn ": " mañana ",
    " mañn ": " mañana ",
    " ayer ": " ayer ",
    " dsp ": " después ",
    " dsps ": " después ",
    " depues ": " después ",
    " antes ": " antes ",
    " pqno ": " por qué no ",
    " pk ": " porque / por qué, según contexto ",
    " xfa ": " por favor ",
    " porfa ": " por favor ",
    " plis ": " por favor ",
    " grax ": " gracias ",
    " de nada ": " de nada ",
    " nqv ": " no quiero verte / nada que ver, según contexto ",
    " nqv? ": " nada que ver? ",
    " tq ": " te quiero ",
    " tkm ": " te quiero mucho ",
    " tqm ": " te quiero mucho ",
    " tm ": " te amo / también, según contexto ",
    " bb ": " bebé ",
    " nena ": " nena ",
    " nene ": " nene ",
    " wapa ": " guapa ",
    " wap@ ": " guapo / guapa ",
    " salu2 ": " saludos ",
    " bss ": " besos ",
    " tk ": " te quiero ",
    " aki ": " aquí ",
    " ai ": " ahí ",
    " ay ": " hay / ay, según contexto ",
    " stoy ": " estoy ",
    " abla ": " habla ",
    " acer ": " hacer ",
    " ke ": " que ",
    " kase ": " qué haces ",
    " asias ": " gracias ",
    " sip ": " sí ",
    " nop ": " no ",
    " sep ": " sí ",
    " nel ": " no ",
    " ok ": " vale / de acuerdo ",
    " oki ": " vale ",
    " okis ": " vale ",
    " va ": " vale ",
    " vdd ": " verdad ",
    " vrdd ": " verdad ",
    " ntc ": " no te creas ",
    " nmms ": " no me digas / no inventes, uso coloquial ",
    " alv ": " a la verga, muy coloquial ",
    " hdp ": " hijo de puta ",
    " ptm ": " puta madre ",
    " wtff ": " what the fuck / qué cojones ",
    
    " u ": " you ",
    " ur ": " your / you're ",
    " r ": " are ",
    " y ": " why ",
    " n ": " and ",
    " bc ": " because ",
    " bcz ": " because ",
    " cuz ": " because ",
    " cos ": " because ",
    " tho ": " though ",
    " tho? ": " though? ",
    " pls ": " please ",
    " plz ": " please ",
    " sry ": " sorry ",
    " soz ": " sorry ",
    " ty ": " thank you ",
    " thx ": " thanks ",
    " tx ": " thanks ",
    " yw ": " you're welcome ",
    " np ": " no problem ",
    " nw ": " no worries ",
    " nvm ": " never mind ",
    " idk ": " I don't know ",
    " idc ": " I don't care ",
    " ik ": " I know ",
    " imo ": " in my opinion ",
    " imho ": " in my humble opinion ",
    " tbh ": " to be honest ",
    " ngl ": " not gonna lie ",
    " fr ": " for real ",
    " rn ": " right now ",
    " atm ": " at the moment ",
    " brb ": " be right back ",
    " bbl ": " be back later ",
    " g2g ": " got to go ",
    " gtg ": " got to go ",
    " ttyl ": " talk to you later ",
    " cya ": " see you ",
    " cu ": " see you ",
    " lmk ": " let me know ",
    " hmu ": " hit me up ",
    " dm ": " direct message ",
    " pm ": " private message ",
    " msg ": " message ",
    " pic ": " picture ",
    " pics ": " pictures ",
    " vid ": " video ",
    " vids ": " videos ",
    " ppl ": " people ",
    " smth ": " something ",
    " sth ": " something ",
    " sb ": " somebody ",
    " s1 ": " someone ",
    " sum1 ": " someone ",
    " any1 ": " anyone ",
    " every1 ": " everyone ",
    " no1 ": " no one ",
    " b4 ": " before ",
    " gr8 ": " great ",
    " l8r ": " later ",
    " m8 ": " mate ",
    " w/ ": " with ",
    " w/o ": " without ",
    " wknd ": " weekend ",
    " tho ": " though ",
    " alr ": " alright ",
    " aight ": " alright ",
    " okk ": " okay ",
    " k ": " okay ",
    " kk ": " okay ",
    " omg ": " oh my god ",
    " omw ": " on my way ",
    " fyi ": " for your information ",
    " asap ": " as soon as possible ",
    " aka ": " also known as ",
    " diy ": " do it yourself ",
    " tmr ": " tomorrow ",
    " tmrw ": " tomorrow ",
    " yday ": " yesterday ",
    " abt ": " about ",
    " bcuz ": " because ",
    " dunno ": " don't know ",
    " lemme ": " let me ",
    " gimme ": " give me ",
    " wanna ": " want to ",
    " gonna ": " going to ",
    " gotta ": " got to ",
    " outta ": " out of ",
    " kinda ": " kind of ",
    " sorta ": " sort of ",
    " lotta ": " a lot of ",
    " ya ": " you / yes, según contexto ",
    " yep ": " yes ",
    " nope ": " no ",
    " yup ": " yes ",
    " nah ": " no ",
    " bro ": " brother / dude ",
    " sis ": " sister ",
    " bae ": " babe / before anyone else ",
    " bby ": " baby ",
    " luv ": " love ",
    " xoxo ": " kisses and hugs ",
    " ilu ": " I love you ",
    " ily ": " I love you ",
    " ilysm ": " I love you so much ",
    " miss u ": " miss you ",
    " cmon ": " come on ",
    " ppl ": " people ",
    " sec ": " second ",
    " mins ": " minutes ",
    " hr ": " hour ",
    " hrs ": " hours ",
    " app ": " application / app ",
    " otp ": " on the phone / one true pairing, según contexto ",
    " afk ": " away from keyboard ",
    " irl ": " in real life ",
    " jk ": " just kidding ",
    " dw ": " don't worry ",
    " mf ": " motherfucker ",
    " wtf ": " what the fuck ",
    " tf ": " the fuck ",
    " bs ": " bullshit ",
    " sus ": " suspicious ",
    " flex ": " presumir / presumir algo ",
    " lowkey ": " discretamente / un poco ",
    " highkey ": " claramente / bastante ",
    " legit ": " de verdad / legítimo ",
    " vibin ": " disfrutando el momento ",
    " gonna b ": " going to be ",
    " ive ": " I have ",
    " im ": " I am ",
    " ive been ": " I have been ",
    " cant ": " cannot ",
    " wont ": " will not ",
    " dont ": " do not ",
    " doesnt ": " does not ",
    " didnt ": " did not ",
    
    " спс ": " спасибо ",
    " хай ": " привет ",
    " хз ": " не знаю ",
    " пасиб ": " спасибо ",
    " хай ": " привет ",
    " хз ": " не знаю ",
    " пж ": " пожалуйста ",
    " плиз ": " пожалуйста ",
    " пож ": " пожалуйста ",
    " прив ": " привет ",
    " хай ": " привет ",
    " даров ": " здорово / hola ",
    " пон ": " понял / понятно ",
    " непон ": " не понял ",
    " ок ": " хорошо / vale ",
    " окей ": " хорошо / vale ",
    " нзч ": " не за что ",
    " не ": " нет ",
    " лан ": " ладно ",
    " ладн ": " ладно ",
    " ща ": " сейчас ",
    " сча ": " сейчас ",
    " щас ": " сейчас ",
    " чз ": " через ",
    " чел ": " человек ",
    " челик ": " человек / tipo ",
    " тя ": " тебя ",
    " те ": " тебе ",
    " мб ": " может быть ",
    " мож ": " может ",
    " хз ": " не знаю ",
    " хзч ": " не знаю что ",
    " хд ": " смех / xd ",
    " лол ": " смешно / LOL ",
    " ору ": " me parto / me río mucho ",
    " жиза ": " жизненно ",
    " крч ": " короче ",
    " кароч ": " короче ",
    " всм ": " в смысле ",
    " ппц ": " капец / qué locura ",
    " капец ": " qué locura / vaya tela ",
    " оч ": " очень ",
    " очн ": " очень ",
    " норм ": " нормально ",
    " нормас ": " нормально / guay ",
    " нормик ": " normal / bien ",
    " збс ": " заебись / muy bien, vulgar ",
    " найс ": " хорошо / nice ",
    " жесть ": " una locura / heavy ",
    " имба ": " muy bueno / roto ",
    " топ ": " genial / top ",
    " рил ": " реально ",
    " пруф ": " доказательство / proof ",
    " пруфы ": " доказательства ",
    " го ": " давай / let's go ",
    " гг ": " good game / fin ",
    " изи ": " легко ",
    " лив ": " выйти / leave ",
    " афк ": " away from keyboard ",
    " кд ": " cooldown ",
    " катка ": " partida ",
    " тим ": " команда / team ",
    " сори ": " извини ",
    " сорян ": " извини ",
    " споки ": " спокойной ночи ",
    " спок ": " спокойной ночи ",
    " др ": " день рождения ",
    " с др ": " с днём рождения ",
    " днюха ": " cumpleaños ",
    " тян ": " chica ",
    " кун ": " chico ",
    " кринж ": " vergüenza ajena / cringe ",
    " вайб ": " ambiente / vibe ",
    " вайбик ": " ambientillo / vibe ",
    " токс ": " tóxico ",
    " токсик ": " tóxico ",
    " душн ": " pesado / aburrido ",
    " душнила ": " pesado / aburrido ",
    " жду ": " espero ",
    " пас ": " paso / no quiero ",
    " пох ": " me da igual, vulgar ",
    " похер ": " me da igual, vulgar ",
    " похуй ": " me da igual, muy vulgar ",
    " блин ": " jo / damn ",
    " бл ": " блин / jo ",
    " пздц ": " desastre / muy fuerte, muy vulgar ",
    " емае ": " madre mía ",
    " ёмаё ": " madre mía ",
    " лс ": " mensajes privados ",
    " в лс ": " por privado ",
    " пм ": " mensaje privado ",
    " инет ": " internet ",
    " инста ": " Instagram ",
    " тг ": " Telegram ",
    " вк ": " VK ",
    " ава ": " avatar / foto de perfil ",
    " авка ": " avatar / foto de perfil ",
    " фотка ": " foto ",
    " видос ": " vídeo ",
    " видик ": " vídeo ",
    " видюха ": " vídeo / tarjeta gráfica, según contexto ",
    " доки ": " documentos ",
    " инфа ": " información ",
    " хата ": " casa / piso ",
    " кв ": " квартира / apartamento ",
    " вид ": " внешний вид / aspecto, según contexto ",
    " чд ": " что делаешь ",
    " чдд ": " что делаешь ",
    " чзх ": " что за хрень ",
    " чё ": " что ",
    " че ": " что ",
    " че как ": " qué tal / cómo va ",
    " ты где ": " donde estás ",
    " мда ": " vaya / pues sí ",
    " ага ": " sí / ajá ",
    " угу ": " sí ",
    " неа ": " no ",
    " да ": " sí ",
    " канеш ": " конечно ",
    " конеш ": " конечно ",
    " ясн ": " ясно ",
    " яснo ": " ясно ",
    " понл ": " понял ",
    " поняла ": " entendí ",
    " хех ": " jeje ",
    " ахах ": " jajaja ",
    " аххах ": " jajaja ",
    " ля ": " wow / jo ",
    " хехе ": " jeje ",
    " мимими ": " cute / tierno ",
    " ня ": " mono / cute ",
    " няш ": " mono / adorable ",
    " няшка ": " persona adorable ",
    " лю ": " люблю / amo ",
    " лю тя ": " te quiero ",
    " люблю ": " amo / quiero ",
    " об ": " об этом / sobre eso, según contexto ",
    " чутка ": " un poco ",
    " ток ": " только ",
    " прост ": " просто ",
    " пжлст ": " пожалуйста ",
    " пжста ": " пожалуйста ",
    " спокн ": " спокойной ночи ",
    " челикс ": " tipo / persona ",
    " работ ": " работа / trabajo ",
    " учёба ": " estudios ",
    " универ ": " universidad ",
    " шара ": " gratis / fácil, según contexto ",
    " домашка ": " deberes ",
    " дз ": " домашнее задание / tarea ",
    " преп ": " profesor ",
    " одногр ": " compañero de grupo ",
    " мес ": " mes ",
    " мин ": " minuto ",
    " сек ": " segundo ",
    " км ": " kilómetro ",
    " щ ": " сейчас, muy abreviado ",
    " пх ": " me da igual / paso, según contexto ",
    " омг ": " о боже / oh my god ",
    " имхо ": " en mi opinión ",
    " лмк ": " дай знать / let me know ",
    " бб ": " пока / bye-bye ",
    " ку ": " привет ",
    " пасиба ": " спасибо ",
    " спасиб ": " спасибо "
    }

    texto = f" {texto} "

    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)

    return normalizar_texto(" ".join(texto.split()))

def detectar_idioma(texto):
    """
    Detecta si el mensaje parece español, inglés, ruso o desconocido.
    """
    palabras_es = [
    "hola", "holaa", "hol", "ola", "buenas", "que", "como", "estas",
    "precio", "opciones", "hablas", "contenido", "puedes", "quiero",
    "tienes", "cuanto", "respondes", "responder", "por aqui",
    "que tal", "sigues ahi", "me vas a responder",
    "vendes", "fotos", "packs", "fotos", "y", "video", "videos",
    "foto", "fotos", "pack", "packs"
    ]

    palabras_en = [
    "hi", "hello", "hey", "how", "price", "options",
    "content", "can", "speak", "want", "what",
    "you", "your", "offer", "have", "are", "there",
    "cost", "will you answer", "why are you not replying",
    "russian", "reply", "answer", "takes", "long",
    "available", "free", "pictures", "photos", "and",
    "video", "videos", "photo", "photos", "pack", "packs"
    ]

    palabras_ru = [
    "привет", "прив", "хай", "здравствуй", "здравствуйте",
    "цена", "цены", "сколько", "стоит", "стоимость",
    "варианты", "вариант", "что есть", "что можно",
    "испански","ты", "тебя", "здесь", "тут", "ответишь", "отвечаешь",
    "контент", "фото", "говоришь", "можешь",
    "почему", "долго", "доступна", "свободна",
    "сексуальное", "поинтереснее", "погорячее",
    "какие", "не знаю","привет", "прив", "хай", "здравствуй", "здравствуйте",
    "цена", "цены", "сколько", "стоит", "стоимость",
    "варианты", "вариант", "что есть", "что можно",
    "испански","ты", "тебя", "здесь", "тут", "ответишь", "отвечаешь",
    "контент", "фото", "говоришь", "можешь",
    "почему", "долго", "доступна", "свободна",
    "сексуальное", "поинтереснее", "погорячее",
    "какие", "не знаю", "онлайн","и", "видео", "фото", "пак", "паки"
    ]

    puntuacion_es = 0
    puntuacion_en = 0
    puntuacion_ru = 0

    for palabra in palabras_es:
        if palabra in texto:
            puntuacion_es += 1

    for palabra in palabras_en:
        if palabra in texto:
            puntuacion_en += 1

    for palabra in palabras_ru:
        if palabra in texto:
            puntuacion_ru += 1

    puntuaciones = {
        "es": puntuacion_es,
        "en": puntuacion_en,
        "ru": puntuacion_ru
    }

    mejor_idioma = max(puntuaciones, key=puntuaciones.get)

    if puntuaciones[mejor_idioma] > 0:
        return mejor_idioma

    return "otro"
def crear_estado_conversacion():
    return {
        "saludo_ya_hecho": False,
        "ultimas_categorias": [],
        "ultimas_respuestas": [],
        "num_mensajes": 0,
        "ultimo_idioma": None
    }
def detectar_consulta_idioma_simple(texto):
    """
    Detecta cuando el mensaje es solo el nombre de un idioma.
    """
    mapa = {
        "ingles": "es",
        "espanol": "es",
        "ruso": "es",

        "english": "en",
        "spanish": "en",
        "russian": "en",

        "английский": "ru",
        "русский": "ru",
        "испанский": "ru"
    }

    return mapa.get(texto.strip().lower())

def parece_texto_basura(texto):
    """
    Detecta textos muy raros o sin estructura.
    Evita tratar palabras rusas normales como basura.
    """
    texto = texto.strip().lower()

    basura_conocida = ["blablabla", "sdkjfh", "qwerty", "asdf", "zzz", "xxx"]
    if texto in basura_conocida:
        return True

    # Si contiene cirílico, no lo tratamos como basura aquí.
    if re.search(r"[а-яё]", texto):
        return False

    # Solo una palabra rara y sin vocales latinas suficientes
    if len(texto.split()) == 1:
        vocales = sum(1 for c in texto if c in "aeiou")
        if len(texto) >= 4 and vocales == 0:
            return True

    return False

def clasificar_mensaje_multiple(texto, idioma, faq_data):
    """
    Devuelve todas las categorías detectadas con su puntuación.
    """
    categorias_detectadas = []

    for categoria, datos_categoria in faq_data.items():
        if idioma not in datos_categoria:
            continue

        palabras_clave = datos_categoria[idioma]["palabras"]
        puntuacion = 0

        for palabra in palabras_clave:
            if palabra in texto:
                puntuacion += 1

        if puntuacion > 0:
            categorias_detectadas.append({
                "categoria": categoria,
                "puntuacion": puntuacion
            })

    return categorias_detectadas

def eliminar_categorias_redundantes(categorias_respondibles):
    """
    Elimina categorías que repiten prácticamente la misma idea.
    """
    nombres = [item["categoria"] for item in categorias_respondibles]
    filtradas = []

    for item in categorias_respondibles:
        categoria = item["categoria"]

        if categoria == "pregunta_venta" and "opciones" in nombres:
            continue

        if categoria == "precio" and "pregunta_precio_detallada" in nombres:
            continue

        filtradas.append(item)

    return filtradas


def crear_estado_conversacion():
    return {
        "saludo_ya_hecho": False,
        "ultimas_categorias": [],
        "ultimas_respuestas": [],
        "num_mensajes": 0
    }

def actualizar_estado_conversacion(estado, categorias_usadas, mensajes_respuesta, idioma=None):
    estado["num_mensajes"] += 1

    for categoria in categorias_usadas:
        estado["ultimas_categorias"].append(categoria)

    for mensaje in mensajes_respuesta:
        estado["ultimas_respuestas"].append(mensaje)

    estado["ultimas_categorias"] = estado["ultimas_categorias"][-5:]
    estado["ultimas_respuestas"] = estado["ultimas_respuestas"][-5:]

    if "saludo" in categorias_usadas:
        estado["saludo_ya_hecho"] = True

    if idioma:
        estado["ultimo_idioma"] = idioma

def es_continuacion_simple(texto):
    texto = texto.strip().lower()

    inicios = [
        "and ", "and, ",
        "y ", "y, ",
        "also ", "also, ",
        "tambien ", "tambien, ",
        "и ", "и, ",
        "еще ", "ещё ", "ещё, ", "еще, "
    ]

    return any(texto.startswith(x) for x in inicios)        
def ordenar_categorias_por_prioridad(categorias_detectadas):
    
    """
    Ordena las categorías según prioridad de negocio y luego por puntuación.
    """
    prioridad = {
        "saludo": 1,
        "opciones": 2,
        "precio": 3,
        "pregunta_precio_detallada": 3,
        "pregunta_venta": 4,
        "disponibilidad": 5,
        "idioma": 6,
        "tiempo_respuesta": 7,
        "preferencia_contenido": 8
    }
    return sorted(
        categorias_detectadas,
        key=lambda x: (prioridad.get(x["categoria"], 999), -x["puntuacion"])
    )

def aplicar_contexto_a_categorias(categorias_respondibles, estado):
    """
    Ajusta categorias segun el contexto reciente.
    """
    categorias_filtradas = []
    nombres = [item["categoria"] for item in categorias_respondibles]

    for item in categorias_respondibles:
        categoria = item["categoria"]

        # Si ya hubo saludo, solo quitamos el saludo
        # cuando venga acompañado de otra categoria.
        if categoria == "saludo" and estado["saludo_ya_hecho"] and len(nombres) > 1:
            continue

        categorias_filtradas.append(item)

    return categorias_filtradas


def calcular_confianza_multiple(categorias_detectadas, texto):
    """
    Calcula la confianza para cada categoría detectada.
    """
    resultado = []

    categorias_faq_claras = [
        "saludo",
        "precio",
        "opciones",
        "disponibilidad",
        "idioma",
        "tiempo_respuesta",
        "pregunta_venta",
        "pregunta_precio_detallada",
        "preferencia_contenido"
    ]

    for item in categorias_detectadas:
        categoria = item["categoria"]
        puntuacion = item["puntuacion"]

        if categoria in categorias_faq_claras:
            if puntuacion >= 2:
                confianza = "alta"
            elif puntuacion >= 1:
                confianza = "media"
            else:
                confianza = "baja"
        else:
            if puntuacion >= 2:
                confianza = "alta"
            elif puntuacion == 1:
                confianza = "media"
            else:
                confianza = "baja"

        resultado.append({
            "categoria": categoria,
            "puntuacion": puntuacion,
            "confianza": confianza
        })

    return resultado

def filtrar_categorias_respondibles(categorias_con_confianza):
    """
    Filtra las categorías que sí se pueden responder automáticamente.
    """
    categorias_permitidas_media = [
        "saludo",
        "precio",
        "opciones",
        "disponibilidad",
        "idioma",
        "tiempo_respuesta",
        "pregunta_venta",
        "pregunta_precio_detallada",
        "preferencia_contenido"
    ]

    respondibles = []

    for item in categorias_con_confianza:
        categoria = item["categoria"]
        confianza = item["confianza"]

        responder_automatico = False

        if confianza == "alta":
            responder_automatico = True
        elif confianza == "media" and categoria in categorias_permitidas_media:
            responder_automatico = True

        if responder_automatico:
            respondibles.append(item)

    return respondibles

def es_mensaje_corto(texto):
    """
    Detecta si el mensaje es muy corto.
    """
    palabras = texto.split()
    return len(palabras) <= 2 or len(texto) <= 8


    
def limpiar_espacios(texto):
    """
    Limpia dobles espacios y espacios raros.
    """
    return " ".join(texto.split())

def combinar_dos_respuestas(resp1, resp2, usados_conectores=None):
    """
    Combina dos respuestas en una sola evitando repetir conectores.
    """
    if usados_conectores is None:
        usados_conectores = []

    if not resp1:
        return resp2
    if not resp2:
        return resp1

    resp1 = resp1.strip()
    resp2 = resp2.strip()

    if resp1.endswith("."):
        resp1 = resp1[:-1]

    conectores_suaves = [
        ". ",
        ", y ",
        ", ademas, ",
        ", y tambien "
    ]

    if resp2 and resp2[0].isupper():
        return f"{resp1}. {resp2}"

    conector = elegir_opcion_no_repetida(conectores_suaves, usados_conectores)
    return f"{resp1}{conector}{resp2}"

def asegurar_punto_final(texto):
    """
    Añade punto final si no acaba en signo válido o emoji.
    """
    texto = texto.strip()
    if not texto:
        return texto

    finales_validos = [".", "!", "?", "😊"]
    if any(texto.endswith(x) for x in finales_validos):
        return texto

    return texto + "."


def empieza_con_alguno(texto, inicios):
    """
    Comprueba si un texto empieza con alguno de los inicios dados.
    """
    texto_lower = texto.lower().strip()
    for inicio in inicios:
        if texto_lower.startswith(inicio.lower()):
            return True
    return False


def quitar_inicio_repetido(texto, idioma="es"):
    """
    Suaviza arranques demasiado repetitivos en mensajes secundarios.
    """
    reemplazos_es = {
        "si, ": "",
        "sí, ": "",
        "claro, ": "",
        "pues, ": "",
        "te cuento, ": "",
        "si quieres, ": "",
        "puedo contarte, ": "",
        "ahora mismo, ": "",
        "ando por aqui, ": "",
        "estoy por aqui, ": ""
    }

    reemplazos_en = {
        "yes, ": "",
        "sure, ": "",
        "well, ": "",
        "if you want, ": "",
        "i can tell you, ": "",
        "right now, ": "",
        "i'm around, ": "",
        "i'm here, ": ""
    }

    reemplazos_ru = {
        "да, ": "",
        "если хочешь, ": "",
        "кстати, ": "",
        "ещё, ": "",
        "и да, ": "",
        "кроме того, ": "",
        "если что, ": ""
    }

    if idioma == "es":
        reemplazos = reemplazos_es
    elif idioma == "en":
        reemplazos = reemplazos_en
    else:
        reemplazos = reemplazos_ru

    texto_mod = texto
    for inicio, reemplazo in reemplazos.items():
        if texto_mod.lower().startswith(inicio):
            texto_mod = reemplazo + texto_mod[len(inicio):]
            break

    return texto_mod.strip()
       
def humanizar_mensajes(lista_mensajes, idioma):
    """
    Hace que una lista de mensajes suene más natural
    y evita repetir conectores dentro de la misma cadena.
    """
    if not lista_mensajes:
        return []

    conectores_es = [
        "Si quieres, ",
        "Tambien, ",
        "Y bueno, ",
        "Ademas, ",
        "Por cierto, ",
        "Y si te sirve, "
    ]

    conectores_en = [
        "",
        "If you want, ",
        "By the way, ",
        "And yes, ",
        "I can also say that "
    ]

    conectores_ru = [
        "Если хочешь, ",
        "Кстати, ",
        "Ещё, ",
        "И да, ",
        "Кроме того, ",
        "Если что, "
    ]

    inicios_naturales_es = [
        "si quieres",
        "tambien",
        "ademas",
        "por cierto",
        "y bueno",
        "y si"
    ]

    inicios_naturales_en = [
        "if you want",
        "by the way",
        "and yes",
        "i can also say that"
    ]

    inicios_naturales_ru = [
        "если хочешь",
        "кстати",
        "ещё",
        "и да",
        "кроме того",
        "если что"
    ]

    if idioma == "es":
        conectores = conectores_es
        inicios_naturales = inicios_naturales_es
    elif idioma == "en":
        conectores = conectores_en
        inicios_naturales = inicios_naturales_en
    else:
        conectores = conectores_ru
        inicios_naturales = inicios_naturales_ru

    mensajes_finales = []
    usados_conectores = []

    for i, mensaje in enumerate(lista_mensajes):
        if not mensaje:
            continue

        mensaje = limpiar_espacios(mensaje)

        if i == 0:
            mensaje = asegurar_punto_final(mensaje)
            mensajes_finales.append(mensaje)
            continue

        mensaje = quitar_inicio_repetido(mensaje, idioma=idioma)

        if not empieza_con_alguno(mensaje, inicios_naturales):
            conector = elegir_opcion_no_repetida(conectores, usados_conectores)
            if conector:
                mensaje = conector + mensaje[:1].lower() + mensaje[1:] if mensaje else mensaje

        mensaje = limpiar_espacios(mensaje)
        mensaje = asegurar_punto_final(mensaje)
        mensajes_finales.append(mensaje)

    return mensajes_finales

def elegir_opcion_no_repetida(opciones, usadas):
    """
    Elige una opción evitando repetirla dentro de la misma cadena.
    Si ya se usaron todas, reinicia.
    """
    disponibles = [op for op in opciones if op not in usadas]

    if not disponibles:
        usadas.clear()
        disponibles = opciones[:]

    elegida = random.choice(disponibles)
    usadas.append(elegida)
    return elegida

def construir_lista_mensajes(categorias_respondibles, idioma, texto, faq_data, estado_conversacion=None):
    """
    Construye una lista de mensajes naturales a partir de varias categorías.
    """
    if not categorias_respondibles:
        return []

    categorias_ordenadas = ordenar_categorias_por_prioridad(categorias_respondibles)
    nombres = [x["categoria"] for x in categorias_ordenadas]

    mensajes = []
    usados = []
    usados_conectores = []
    especial = None
    
    # Caso especial: saludo repetido sin mas categorias
    if nombres == ["saludo"] and estado_conversacion is not None:
        if estado_conversacion.get("saludo_ya_hecho", False):
            return [generar_respuesta_saludo_repetido(idioma)]
    
    # Caso especial: saludo + disponibilidad
    if "saludo" in nombres and "disponibilidad" in nombres:
        especial = generar_respuesta_combinada_especial(
        ["saludo", "disponibilidad"],
        idioma
    )

    if especial:
        mensajes.append(especial)
        usados.append(especial.lower())

        # Quitamos esas categorias del resto para no repetirlas
        categorias_ordenadas = [
            x for x in categorias_ordenadas
            if x["categoria"] not in ["saludo", "disponibilidad"]
        ]
        nombres = [x["categoria"] for x in categorias_ordenadas]
        
   # Separar saludo si existe
    tiene_saludo = "saludo" in nombres
    resto = [x for x in categorias_ordenadas if x["categoria"] != "saludo"]

    # Si ya generamos un mensaje especial y no queda nada más, devolvemos
    if mensajes and not categorias_ordenadas:
        return mensajes

    # Caso 1: solo saludo
    if tiene_saludo and not resto and not mensajes:
        r = generar_respuesta("saludo", idioma, texto, faq_data, usados)
        mensajes.append(r)
        usados.append(r.lower())
        return mensajes

    # Caso 2: una sola categoría sin saludo
    if not tiene_saludo and len(resto) == 1 and not mensajes:
        r = generar_respuesta(resto[0]["categoria"], idioma, texto, faq_data, usados)
        mensajes.append(r)
        usados.append(r.lower())
        return mensajes

    # Caso 3: saludo + una categoría
    if tiene_saludo and len(resto) == 1 and not mensajes:
        r1 = generar_respuesta("saludo", idioma, texto, faq_data, usados)
        usados.append(r1.lower())

        r2 = generar_respuesta(resto[0]["categoria"], idioma, texto, faq_data, usados)
        usados.append(r2.lower())

        mensajes.append(combinar_dos_respuestas(r1, r2, usados_conectores))
        return mensajes

    usadas = []

    # Primer mensaje: saludo + principal, o principal + secundaria
    if tiene_saludo and resto:
        principal = resto[0]["categoria"]

        r1 = generar_respuesta("saludo", idioma, texto, faq_data, usados)
        usados.append(r1.lower())

        r2 = generar_respuesta(principal, idioma, texto, faq_data, usados)
        usados.append(r2.lower())

        mensajes.append(combinar_dos_respuestas(r1, r2, usados_conectores))
        usadas.append(principal)

    elif len(resto) >= 2:
        c1 = resto[0]["categoria"]
        c2 = resto[1]["categoria"]

        r1 = generar_respuesta(c1, idioma, texto, faq_data, usados)
        usados.append(r1.lower())

        r2 = generar_respuesta(c2, idioma, texto, faq_data, usados)
        usados.append(r2.lower())

        mensajes.append(combinar_dos_respuestas(r1, r2, usados_conectores))
        usadas.extend([c1, c2])

    elif len(resto) == 1:
        r = generar_respuesta(resto[0]["categoria"], idioma, texto, faq_data, usados)
        mensajes.append(r)
        usados.append(r.lower())
        usadas.append(resto[0]["categoria"])

    # Categorías restantes: agrupar hasta 3 por mensaje
    pendientes = [x["categoria"] for x in resto if x["categoria"] not in usadas]

    for i in range(0, len(pendientes), 3):
        grupo = pendientes[i:i+3]
        partes = []

        for categoria in grupo:
            r = generar_respuesta(categoria, idioma, texto, faq_data, usados)
            partes.append(r)
            usados.append(r.lower())

        mensaje_grupo = None
        for parte in partes:
            if mensaje_grupo is None:
                mensaje_grupo = parte
            else:
                mensaje_grupo = combinar_dos_respuestas(mensaje_grupo, parte, usados_conectores)

        if mensaje_grupo:
            mensajes.append(mensaje_grupo)

    return mensajes
    
def calcular_confianza(categoria, puntuacion, texto):
    """
    Asigna un nivel de confianza según categoría, puntuación y longitud del mensaje.
    """
    if categoria == "no_detectada":
        return "baja"

    categorias_faq_claras = [
    "saludo",
    "precio",
    "opciones",
    "disponibilidad",
    "idioma",
    "tiempo_respuesta",
    "pregunta_venta",
    "pregunta_precio_detallada",
    "preferencia_contenido"
    ]

    if categoria in categorias_faq_claras:
        if puntuacion >= 2:
            return "alta"
        elif puntuacion >= 1:
            return "media"
        else:
            return "baja"

    if puntuacion >= 2:
        return "alta"
    elif puntuacion == 1:
        return "media"
    else:
        return "baja"


def decidir_respuesta_automatica(categoria, confianza):
    """
    Decide si el sistema debe responder automáticamente.
    """
    if categoria == "no_detectada":
        return False

    categorias_permitidas_media = [
        "saludo",
        "precio",
        "opciones",
        "disponibilidad",
        "idioma",
        "tiempo_respuesta"
    ]

    if confianza == "alta":
        return True

    if confianza == "media" and categoria in categorias_permitidas_media:
        return True

    return False

def construir_respuesta_por_bloques(categoria, idioma, texto, faq_data):
    """
    Construye una respuesta combinando apertura + cuerpo + cierre.
    """
    datos = faq_data[categoria][idioma]

    apertura = random.choice(datos["aperturas"])

    if es_mensaje_corto(texto):
        cuerpo = random.choice(datos["cuerpos_cortos"])

        # Si es saludo corto, no añadir cierre para evitar cosas como "😍 😊"
        return f"{apertura} {cuerpo}".strip()

    cuerpo = random.choice(datos["cuerpos_normales"])
    cierre = random.choice(datos["cierres"])

    return f"{apertura}, {cuerpo}{cierre}".strip()

def generar_respuesta(categoria, idioma, texto, faq_data, usados=None):
    """
    Genera una respuesta según la categoría y el tipo de mensaje.
    Intenta evitar repeticiones si se le pasa 'usados'.
    """
    if usados is None:
        usados = []

    if categoria in faq_data and idioma in faq_data[categoria]:
        categorias_por_bloques = ["saludo"]

        if categoria in categorias_por_bloques:
            return construir_respuesta_por_bloques(categoria, idioma, texto, faq_data)

        datos = faq_data[categoria][idioma]

        respuestas_posibles = []

        if "respuestas_normales" in datos:
            respuestas_posibles.extend(datos["respuestas_normales"])

        if "respuestas" in datos:
            respuestas_posibles.extend(datos["respuestas"])

        return elegir_mejor_respuesta(respuestas_posibles, usados, idioma)

    return None

def generar_respuesta_saludo_repetido(idioma):
    """
    Respuesta natural cuando el usuario vuelve a saludar dentro
    de una conversación ya iniciada.
    """
    respuestas = {
        "es": [
            "Aqui sigo 😊",
            "Si, te leo.",
            "Sigo por aqui.",
            "Aqui estoy.",
            "Si 😊"
        ],
        "en": [
            "Still here 😊",
            "Yes, I'm here.",
            "I'm still around.",
            "Yep 😊",
            "I'm here."
        ],
        "ru": [
            "Я тут 😊",
            "Да, я здесь.",
            "Я все еще тут.",
            "Да 😊",
            "Я на месте.",
            "Тут 😊",
            "Да, я здесь сейчас.",
            "Все еще тут 😊"
        ]
    }

    if idioma in respuestas:
        return random.choice(respuestas[idioma])

    return "Aqui sigo 😊"

def generar_respuesta_combinada_especial(categorias, idioma):
    """
    Devuelve una respuesta especial para combinaciones frecuentes.
    """
    categorias_set = set(categorias)

    combinaciones = {
        ("saludo", "disponibilidad"): {
            "es": [
                "Hola 😊 estoy por aquí, aunque a veces puedo tardar un poquito en responder.",
                "Holaa 😊 sí, aquí estoy, pero puede que tarde un poco en contestar.",
                "Buenas 😊 te leo en cuanto tenga un rato.",
                "Hey 😊 estoy por aquí, aunque ahora mismo voy un poco liada."
            ],
            "en": [
                "Hello 😊 I'm here, although I may take a little while to reply.",
                "Hi 😊 yes, I'm around, but I might reply a little later.",
                "Hey 😊 I'm here, although I'm a little busy right now.",
                "Hello 😊 I'll read you as soon as I have a moment."
            ],
            "ru": [
                "Привет 😊 я здесь, хотя иногда могу отвечать не сразу.",
                "Приветик 😊 да, я тут, но могу немного задержаться с ответом.",
                "Хай 😊 я на месте, просто иногда отвечаю не сразу.",
                "Привет 😊 как будет минутка, отвечу."
            ]
        }
    }

    for combo, textos in combinaciones.items():
        if set(combo) == categorias_set:
            if idioma in textos:
                return random.choice(textos[idioma])

    return None

def penalizacion_repeticion(texto, usados, idioma):
    """
    Devuelve una puntuación de repetición.
    Cuanto más alta, peor.
    """
    texto_lower = texto.lower()

    palabras_control_es = [
        "depende",
        "opcion",
        "opciones",
        "si quieres",
        "disponible"
    ]

    palabras_control_en = [
        "depends",
        "option",
        "options",
        "if you want",
        "available"
    ]

    palabras_control_ru = [
        "если хочешь",
        "вариант",
        "варианты",
        "цена",
        "доступно"
    ]

    if idioma == "es":
        palabras_control = palabras_control_es
    elif idioma == "en":
        palabras_control = palabras_control_en
    else:
        palabras_control = palabras_control_ru

    score = 0

    for palabra in palabras_control:
        if palabra in texto_lower and any(palabra in u for u in usados):
            score += 1

    return score

def elegir_mejor_respuesta(respuestas_posibles, usados, idioma):
    """
    Elige una respuesta intentando evitar repeticiones.
    """
    if not respuestas_posibles:
        return None

    candidatas = []

    for r in respuestas_posibles:
        score = penalizacion_repeticion(r, usados, idioma)
        candidatas.append((score, r))

    candidatas.sort(key=lambda x: x[0])

    # Nos quedamos con las de menor penalizacion
    mejor_score = candidatas[0][0]
    mejores = [r for score, r in candidatas if score == mejor_score]

    return random.choice(mejores)

def procesar_mensaje(mensaje, faq_data, estado):
    mensaje_normalizado = normalizar_texto_extendido(mensaje)

    # Detect base language
    idioma_detectado = detectar_idioma(mensaje_normalizado)

    # Simple language-only query
    idioma_simple = detectar_consulta_idioma_simple(mensaje_normalizado)
    if idioma_simple:
        respuesta = generar_respuesta("idioma", idioma_simple, mensaje_normalizado, faq_data, usados=[])
        return {
            "idioma": idioma_simple,
            "categorias_detectadas": [{"categoria": "idioma", "puntuacion": 1, "confianza": "media"}],
            "categorias_respondibles": [{"categoria": "idioma", "puntuacion": 1, "confianza": "media"}],
            "mensajes_respuesta": [respuesta]
        }

    # Short continuation like "and videos", "y packs", "и фото"
    if es_continuacion_simple(mensaje_normalizado):
        idioma_continuacion = (
            idioma_detectado
            if idioma_detectado != "otro"
            else estado.get("ultimo_idioma", "en")
        )

        ultimas = estado.get("ultimas_categorias", [])

        categorias_validas = [
            "opciones",
            "pregunta_venta",
            "pregunta_precio_detallada",
            "precio",
            "preferencia_contenido"
        ]

        ultima_categoria_util = None
        for cat in reversed(ultimas):
            if cat in categorias_validas:
                ultima_categoria_util = cat
                break

        if ultima_categoria_util:
            respuesta = generar_respuesta(
                ultima_categoria_util,
                idioma_continuacion,
                mensaje_normalizado,
                faq_data,
                usados=[]
            )

            mensajes_respuesta = [respuesta]
            categorias_usadas = [ultima_categoria_util]

            actualizar_estado_conversacion(
                estado,
                categorias_usadas,
                mensajes_respuesta,
                idioma=idioma_continuacion
            )

            return {
                "idioma": idioma_continuacion,
                "categorias_detectadas": [
                    {
                        "categoria": ultima_categoria_util,
                        "puntuacion": 1,
                        "confianza": "media"
                    }
                ],
                "categorias_respondibles": [
                    {
                        "categoria": ultima_categoria_util,
                        "puntuacion": 1,
                        "confianza": "media"
                    }
                ],
                "mensajes_respuesta": mensajes_respuesta
            }

    if parece_texto_basura(mensaje_normalizado):
        return {
            "idioma": "desconocido",
            "categorias_detectadas": [],
            "categorias_respondibles": [],
            "mensajes_respuesta": [
                "Lo siento, no he entendido bien el mensaje. ¿Puedes escribirlo de otra forma?"
            ]
        }

    idioma = idioma_detectado

    if idioma == "otro":
        return {
            "idioma": "otro",
            "categorias_detectadas": [],
            "categorias_respondibles": [],
            "mensajes_respuesta": [
                "Sorry, I can only reply in Spanish, English or Russian right now."
            ]
        }

    categorias_detectadas = clasificar_mensaje_multiple(mensaje_normalizado, idioma, faq_data)
    categorias_con_confianza = calcular_confianza_multiple(categorias_detectadas, mensaje_normalizado)
    categorias_respondibles = filtrar_categorias_respondibles(categorias_con_confianza)
    categorias_respondibles = eliminar_categorias_redundantes(categorias_respondibles)
    categorias_respondibles = aplicar_contexto_a_categorias(categorias_respondibles, estado)

    if not categorias_respondibles:
        if idioma == "es":
            mensajes_respuesta = [
                "Lo siento, no he entendido bien el mensaje. ¿Puedes escribirlo de otra forma?"
            ]
        elif idioma == "ru":
            mensajes_respuesta = [
                "Извини, я не совсем поняла сообщение. Можешь написать по-другому?"
            ]
        else:
            mensajes_respuesta = [
                "Sorry, I didn’t fully understand the message. Can you rephrase it?"
            ]
    else:
        mensajes_respuesta = construir_lista_mensajes(
            categorias_respondibles,
            idioma,
            mensaje_normalizado,
            faq_data,
            estado
        )

    mensajes_respuesta = humanizar_mensajes(mensajes_respuesta, idioma)
    categorias_usadas = [x["categoria"] for x in categorias_respondibles]
    actualizar_estado_conversacion(estado, categorias_usadas, mensajes_respuesta, idioma=idioma)

    return {
        "idioma": idioma,
        "categorias_detectadas": categorias_con_confianza,
        "categorias_respondibles": categorias_respondibles,
        "mensajes_respuesta": mensajes_respuesta
    }

if __name__ == "__main__":
    faq_data = cargar_faqs()
    estado = crear_estado_conversacion()

    while True:
        mensaje_usuario = input("\nEscribe el mensaje del usuario (o 'salir' para terminar): ")

        if mensaje_usuario.lower().strip() == "salir":
            print("Programa finalizado.")
            break

        resultado = procesar_mensaje(mensaje_usuario, faq_data, estado)

        print("\nRESULTADO")
        print("Mensaje:", mensaje_usuario)
        print("Idioma:", resultado["idioma"])
        print("\nCategorías detectadas:")
        for item in resultado["categorias_detectadas"]:
            print(
                f" - {item['categoria']} | puntuacion={item['puntuacion']} | confianza={item['confianza']}"
            )

        print("\nMensajes de respuesta:")
        for i, msg in enumerate(resultado["mensajes_respuesta"], start=1):
            print(f"Mensaje {i}: {msg}")
