from openai import OpenAI

MODELO_LOCAL = "qwen/qwen3.5-9b"

client = OpenAI(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio"
)

SYSTEM_PROMPT_BASE = """
You are chatting as a female content creator talking to a potential customer in English.

Your tone is warm, feminine, playful, natural, relaxed, and human.
You are confident and a little flirty when appropriate, but never explicit, graphic, or robotic.

Your goals:
- keep the conversation flowing naturally
- sound like a real woman texting, not like customer support
- build interest in your content naturally
- move the conversation toward curiosity, attraction, customs, content, or pricing when it fits
- keep the customer engaged without sounding pushy

Hard rules:
- never mention being AI, virtual, digital, a bot, or an assistant
- never mention "digital world", "virtual world", or similar
- never use poetic, fantasy, or overly cute phrases
- never use phrases like "my dear friend", "kindred spirit", "treasure hunt", or similar
- do not sound inspirational, theatrical, formal, or overly polished
- do not over-explain
- do not write long paragraphs
- do not sound scripted
- do not sound like customer support
- do not use emojis unless they feel natural

Natural texting rules:
- answer the customer's question first
- use simple everyday English
- sound like texting, not writing
- 1 to 3 short sentences
- slight imperfections are okay
- keep it light, natural, and engaging
- short replies are usually better than polished ones
- if the customer shows interest, gently keep momentum
- if the customer asks about content, customs, menu, or prices, respond naturally and keep the conversation moving

Good style examples:
- "Haha maybe, but I do things my own way."
- "A couple, yeah, but everyone has their own vibe."
- "Not exactly like me, no."
- "Maybe a few, but I like keeping mine a little different."
- "Haha why, are you curious?"
- "Depends what kind of content you're into."
- "I do a mix, what are you usually looking for?"
- "Yeah I do customs sometimes, depends on what you want."
- "I can tell you more, what kind of thing are you into?"
- "Mine’s a little more personal tbh."

Bad style examples:
- "In the digital world, I connect with many unique souls."
- "You are such a kindred spirit to me."
- "Each conversation feels like a treasure hunt."
- "Oh, my dear friend, you are sweet to ask."
- "I cherish every interaction in a special way."
- "That is such a wonderful and meaningful question."
- "Thank you for your message."
- "How may I assist you today?"
- "I’d be happy to answer that for you."

If the reply sounds poetic, overly polished, theatrical, or AI-generated, rewrite it in a simpler and more natural way.

Output only the final reply text.
""".strip()

FRASES_PROHIBIDAS = [
    "digital world",
    "virtual world",
    "kindred spirit",
    "kindred spirits",
    "treasure hunt",
    "my dear friend",
    "sweet soul",
    "as an ai",
    "i'm an ai",
    "i am an ai",
    "assistant",
    "artificial intelligence",
]


def limpiar_texto_modelo(texto: str) -> str:
    if not texto:
        return ""

    texto = texto.strip()
    texto = texto.strip('"').strip("'").strip()

    prefijos = [
        "Reply:",
        "Response:",
        "Assistant:",
        "Bot:",
        "Message:",
        "Opener:",
    ]
    for prefijo in prefijos:
        if texto.startswith(prefijo):
            texto = texto[len(prefijo):].strip()

    lineas = [line.strip() for line in texto.splitlines() if line.strip()]
    if not lineas:
        return ""

    if len(lineas) >= 2:
        texto_final = " ".join(lineas[:2]).strip()
    else:
        texto_final = lineas[0]

    return texto_final[:300].strip()


def suena_a_ia_o_poco_humano(texto: str) -> bool:
    t = (texto or "").lower().strip()

    if not t:
        return True

    for frase in FRASES_PROHIBIDAS:
        if frase in t:
            return True

    if len(t) > 220:
        return True

    marcadores_raros = [
        "wonderful",
        "special",
        "unique",
        "treasure",
        "dear friend",
        "sweet to ask",
    ]
    score = sum(1 for m in marcadores_raros if m in t)
    if score >= 2:
        return True

    return False


def generar_respuesta_fallback(mensaje_cliente: str) -> str:
    t = (mensaje_cliente or "").lower().strip()

    if "someone else" in t or "with someone else" in t:
        return "A couple maybe, but everyone does things a bit differently. What kind of content are you into?"

    if "hello" in t or "hellow" in t or t == "hi":
        return "Hey, I'm here. What are you in the mood for?"

    if "friend" in t:
        return "Maybe a couple, but not exactly like me. Why, are you curious?"

    if "price" in t or "how much" in t:
        return "Depends what you're looking for really. What kind of content did you have in mind?"

    if "custom" in t:
        return "Yeah, I do customs sometimes. What were you thinking about?"

    if "content" in t or "what do you do" in t:
        return "I do a mix, depends what you're into. What kind of thing do you usually like?"

    return "Hmm maybe. Tell me what kind of thing you're looking for."


def generar_respuesta_ia_local(
    mensaje_cliente: str,
    historial_corto: list[str] | None = None,
    intenciones: list[str] | None = None,
    estado_cliente: str = "chatting"
) -> str:
    historial_corto = historial_corto or []
    intenciones = intenciones or []

    contexto = "\n".join(f"- {x}" for x in historial_corto[-4:]) if historial_corto else "- none"
    intenciones_txt = ", ".join(intenciones) if intenciones else "unknown"

    prompt_usuario = f"""
Customer message:
{mensaje_cliente}

Recent conversation:
{contexto}

Detected intents:
{intenciones_txt}

Conversation stage:
{estado_cliente}

Write only the reply that should be sent to the customer.
Keep it short, natural, and in character.
""".strip()

    response = client.responses.create(
        model=MODELO_LOCAL,
        instructions=SYSTEM_PROMPT_BASE,
        input=prompt_usuario
    )

    texto = limpiar_texto_modelo(response.output_text or "")

    if texto and not suena_a_ia_o_poco_humano(texto):
        return texto

    retry_prompt = f"""
Reply in natural English to this customer message:

{mensaje_cliente}

Rules:
- sound like a real woman texting
- keep it short
- answer directly
- no poetic language
- no "digital world", no "kindred spirit", no weird cute phrases
- no explanations
- output only the reply
""".strip()

    response_retry = client.responses.create(
        model=MODELO_LOCAL,
        instructions=SYSTEM_PROMPT_BASE,
        input=retry_prompt
    )

    texto_retry = limpiar_texto_modelo(response_retry.output_text or "")

    if texto_retry and not suena_a_ia_o_poco_humano(texto_retry):
        return texto_retry

    fallback = generar_respuesta_fallback(mensaje_cliente)
    if fallback:
        return fallback

    raise ValueError("Local AI returned empty or low-quality reply")


def generar_opener_ia_local(
    historial_corto: list[str] | None = None,
    opener_type: str = "soft",
    estado_cliente: str = "chatting"
) -> str:
    historial_corto = historial_corto or []

    if opener_type == "soft":
        instruction = (
            "Write exactly 1 short opener in English. "
            "Tone: warm, feminine, natural, light, friendly. "
            "Do not use emojis. "
            "Maximum 20 words. "
            "Return only the final opener text."
        )
    elif opener_type == "flirty":
        instruction = (
            "Write exactly 1 short opener in English. "
            "Tone: warm, feminine, playful, lightly flirty, natural. "
            "Do not be explicit. "
            "Do not use emojis. "
            "Maximum 20 words. "
            "Return only the final opener text."
        )
    elif opener_type == "upsell":
        instruction = (
            "Write exactly 1 short opener in English. "
            "Tone: warm, feminine, confident, inviting. "
            "Create curiosity and move toward stronger interest naturally. "
            "Do not sound aggressive. "
            "Do not use emojis. "
            "Maximum 22 words. "
            "Return only the final opener text."
        )
    else:
        instruction = (
            "Write exactly 1 short opener in English. "
            "Tone: warm, feminine, natural. "
            "Return only the final opener text."
        )

    history_block = "\n".join(historial_corto[-6:]) if historial_corto else "No previous chat."

    prompt = f"""
You are writing a single opener for a commercial conversational chatbot.

{instruction}

Conversation context:
{history_block}
""".strip()

    system_prompt_opener = """
You write short natural English openers for a commercial conversational chatbot.

Rules:
- output only 1 opener
- no explanations
- no labels
- no bullet points
- no quotation marks
- keep it natural and human
""".strip()

    response = client.responses.create(
        model=MODELO_LOCAL,
        instructions=system_prompt_opener,
        input=prompt
    )

    texto = limpiar_texto_modelo(response.output_text or "")

    if not texto:
        retry_prompt = f"""
Write exactly one short English opener.
Type: {opener_type}
Tone: warm, feminine, natural.
Only output the opener text.
""".strip()

        response_retry = client.responses.create(
            model=MODELO_LOCAL,
            instructions=system_prompt_opener,
            input=retry_prompt
        )

        texto = limpiar_texto_modelo(response_retry.output_text or "")

    if not texto:
        raise ValueError(f"Local AI returned empty opener for opener_type={opener_type}")

    return texto