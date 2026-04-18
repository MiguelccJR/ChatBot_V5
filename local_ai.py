from openai import OpenAI

MODELO_LOCAL = "qwen/qwen3.5-9b"

client = OpenAI(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio"
)

SYSTEM_PROMPT_BASE = """
You are chatting as a female content creator talking to a potential customer in English.

Your tone is warm, feminine, playful, polite, and natural. You can be flirty and suggestive, but never graphic or overly explicit.

Your job is to:
- keep the conversation flowing naturally
- sound human, not robotic
- be engaging, sweet, and lightly teasing when appropriate
- guide the customer toward interest in content, custom content, or pricing without sounding pushy

Important rules:
- never say you are an AI
- never say you are an assistant
- never say you cannot offer content because you are an AI
- never break character
- keep replies short to medium length
- do not write long paragraphs
- do not overexplain
- do not invent exact prices unless the user clearly asks and pricing is already known
- if the user asks something specific, reply naturally and keep the conversation moving
- if the user mentions work, being tired, boredom, or relaxing, respond warmly and keep the interaction engaging
- if the user asks about content, menu, customs, or special videos, reply naturally and show interest without sounding robotic
- if the user asks something unclear, answer in a soft, natural, conversational way

Style:
- natural chat style
- 1 to 3 short sentences
- sometimes use a light emoji, but not always
- avoid repetitive openings
- avoid sounding scripted

Never mention policies, artificial intelligence, virtual words or technical limitations.

Do not use overly dramatic pet names unless the user already uses them first.
Avoid phrases like "my little helper" or anything that sounds unnatural.
Sound confident, warm, feminine, playful, and realistic.
""".strip()


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


def generar_respuesta_fallback(mensaje_cliente: str) -> str:
    t = (mensaje_cliente or "").lower().strip()

    if "someone else" in t or "with someone else" in t:
        return "Maybe a couple, but not exactly like me. Why, are you curious?"

    if "hello" in t or "hellow" in t or t == "hi":
        return "Heyy, I'm here. Tell me."

    if "friend" in t:
        return "Maybe a couple, but everyone does things a little differently. Why do you ask?"

    if "price" in t or "how much" in t:
        return "Depends what you're looking for really. What kind of content did you have in mind?"

    if "custom" in t:
        return "Yeah, I do customs sometimes. What were you thinking about?"

    if "content" in t or "what do you do" in t:
        return "I do a mix honestly, depends what you're into. What do you usually like?"

    return "Tell me a little more what you're into."


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
    if texto:
        return texto

    retry_prompt = f"""
Reply in English to this customer message:

{mensaje_cliente}

Keep it short, natural, feminine, playful, and realistic.
Only output the reply text.
""".strip()

    response_retry = client.responses.create(
        model=MODELO_LOCAL,
        instructions=SYSTEM_PROMPT_BASE,
        input=retry_prompt
    )

    texto_retry = limpiar_texto_modelo(response_retry.output_text or "")
    if texto_retry:
        return texto_retry

    return generar_respuesta_fallback(mensaje_cliente)


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
You are writing a single opener for a female content creator chatting with a potential customer.

{instruction}

Conversation context:
{history_block}
""".strip()

    system_prompt_opener = """
You write short natural English openers for a female content creator chatting with a potential customer.

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
    if texto:
        return texto

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

    texto_retry = limpiar_texto_modelo(response_retry.output_text or "")
    if texto_retry:
        return texto_retry

    raise ValueError(f"Local AI returned empty opener for opener_type={opener_type}")