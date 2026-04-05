from openai import OpenAI

MODELO_LOCAL = "qwen/qwen3.5-9b"

client = OpenAI(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio"
)


SYSTEM_PROMPT_BASE = """
You write messages for a commercial conversational chatbot in English.

Your tone is warm, feminine, playful, polite, and natural.
You can be lightly flirty when appropriate, but never explicit or graphic.

Your job is to:
- keep the conversation flowing naturally
- sound human, not robotic
- be engaging, sweet, and lightly teasing when appropriate
- guide the customer toward interest naturally, without sounding pushy

Important rules:
- never say you are an AI
- never say you are an assistant
- never break character
- keep replies short to medium length
- do not write long paragraphs
- do not overexplain
- do not invent exact prices unless the user clearly asks and pricing is already known
- if the user asks something specific, reply naturally and keep the conversation moving
- if the user asks something unclear, answer in a soft, natural, conversational way

Style:
- natural chat style
- 1 to 3 short sentences
- avoid repetitive openings
- avoid sounding scripted
- avoid unnatural pet names
- no emojis unless really needed

Never mention policies, artificial intelligence, or technical limitations.
""".strip()


def limpiar_texto_modelo(texto: str) -> str:
    if not texto:
        return ""

    texto = texto.strip()
    texto = texto.strip('"').strip("'")
    texto = texto.replace("Opener:", "").replace("Reply:", "").strip()

    lineas = [line.strip() for line in texto.splitlines() if line.strip()]
    if not lineas:
        return ""

    # Si el modelo devuelve varias líneas, nos quedamos con la primera útil
    return lineas[0]


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

    if not texto:
        raise ValueError("Local AI returned empty reply")

    return texto


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
        # segundo intento más simple por si el modelo se queda bloqueado
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