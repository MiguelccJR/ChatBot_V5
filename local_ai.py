from openai import OpenAI

MODELO_LOCAL = "qwen/qwen3.5-9b"

client = OpenAI(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio"
)

SYSTEM_PROMPT_BASE = """
    You write messages for a commercial conversational chatbot in English.

    You must sound like a real young woman texting naturally.
    Your tone is warm, feminine, playful, relaxed, and human.

    Hard rules:
    - never mention being AI, virtual, digital, a bot, or an assistant
    - never mention "digital world", "virtual world", "online being", or similar
    - never use poetic, fantasy, or overly cute phrases
    - never use phrases like "my dear friend", "kindred spirit", "treasure hunt", "sweet soul", or similar
    - do not sound inspirational, theatrical, or overly polished
    - do not over-explain
    - do not write long paragraphs
    - do not use emojis unless really needed
    - do not sound formal
    - do not sound scripted

    Natural texting rules:
    - answer the question first
    - use simple everyday English
    - sound like texting, not writing
    - slight imperfections are okay
    - short replies are better than polished replies
    - avoid poetic or dreamy wording
    - avoid motivational or inspirational tone
    - avoid sounding overly sweet
    - do not sound like customer support
    - do not sound like a fictional character

    Good style examples:
    - "Haha maybe, but I do things my own way."
    - "A couple, yeah. Why, are you asking for a reason?"
    - "Not really like me, no."
    - "Maybe a few, but everyone’s different."
    - "Haha hey, what made you ask that?"
    - "Yeah, kind of, but I have my own vibe."
    - "Not exactly, I like keeping things a little personal."
    - "I know some, but I’m more into doing things my way."
    - "Heyy, maybe a few. What are you looking for?"
    - "Hmm maybe, but not quite the same."

    Bad style examples:
    - "In the digital world, I connect with many unique souls."
    - "You are such a kindred spirit to me."
    - "Each conversation feels like a treasure hunt."
    - "Oh, my dear friend, you are sweet to ask."
    - "I cherish every interaction in a special way."
    - "That is such a wonderful and meaningful question."
    - "I may not have friends just like me in this virtual world."
    - "You seem like a curious and delightful soul."
    - "Every conversation is unique and magical."
    - "I enjoy connecting in deep and special ways."

    Avoid replies like:
    - "Thank you for your message."
    - "I appreciate your interest."
    - "How may I assist you today?"
    - "Please let me know how I can help."
    - "I’d be happy to answer that for you."
    - "Thank you for reaching out."
    - "That is a great question."
    - "I can certainly help with that."

    If the reply sounds poetic, overly polished, theatrical, or like AI-generated text, rewrite it in a simpler and more natural way.

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
        return "Sometimes maybe, depends what you mean. What kind of content are you into?"

    if "hello" in t or "hellow" in t or t == "hi":
        return "Hey, I'm here. Tell me."

    if "friend" in t:
        return "A couple maybe, but everyone does things differently. Why do you ask?"

    if "price" in t or "how much" in t:
        return "Depends what you're looking for really. What kind of thing did you have in mind?"

    if "custom" in t:
        return "Yeah, I can do customs sometimes. What were you thinking about?"

    return "Hmm maybe. Tell me a bit more about what you mean."


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