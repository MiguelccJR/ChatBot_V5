import re
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

SYSTEM_PROMPT_OPENER = """
You are Mia, a female content creator on OnlyFans.
You are texting one of your customers to restart the conversation.
YOU are sending this message. The customer RECEIVES it.

Example of what you should output:
"Hey, been a while! Was thinking about you 😊"
"Miss talking to you, what have you been up to?"
"Hey stranger, you've been quiet lately 👀"

Now write a NEW original message in the same style.
Output ONLY the message text. No labels, no explanations, no quotes.
""".strip()


def quitar_think_tags(texto: str) -> str:
    """Removes <think>...</think> blocks that Qwen outputs before answering."""
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    return texto.strip()


def extraer_texto_respuesta(choice) -> str:
    """
    Qwen3 puts the reply in reasoning_content when it runs out of tokens.
    This tries to extract the actual answer from wherever it ended up.
    Priority: content -> last paragraph of reasoning_content
    """
    msg = choice.message

    content = (getattr(msg, "content", None) or "").strip()
    if content:
        return quitar_think_tags(content)

    reasoning = (getattr(msg, "reasoning_content", None) or "").strip()
    if reasoning:
        for sep in ["\n\nFinal answer:", "\n\nAnswer:", "\n\nReply:", "\n\n---"]:
            if sep in reasoning:
                return reasoning.split(sep)[-1].strip()
        parrafos = [p.strip() for p in reasoning.split("\n\n") if p.strip()]
        if parrafos:
            return parrafos[-1]

    return ""


def limpiar_texto_modelo(texto: str) -> str:
    if not texto:
        return ""

    texto = quitar_think_tags(texto)

    if not texto:
        return ""

    texto = texto.strip().strip('"').strip("'").strip()

    prefijos = ["Reply:", "Response:", "Assistant:", "Bot:", "Message:", "Opener:"]
    for prefijo in prefijos:
        if texto.startswith(prefijo):
            texto = texto[len(prefijo):].strip()

    lineas = [line.strip() for line in texto.splitlines() if line.strip()]
    if not lineas:
        return ""

    texto_final = " ".join(lineas[:3]).strip()
    return texto_final[:400].strip()


def construir_mensajes_historial(historial_corto: list[str]) -> list[dict]:
    messages = []
    for linea in historial_corto:
        linea = linea.strip()
        if linea.startswith("user:"):
            content = linea[5:].strip()
            if content:
                messages.append({"role": "user", "content": content})
        elif linea.startswith("assistant:"):
            content = linea[10:].strip()
            if content:
                messages.append({"role": "assistant", "content": content})
    return messages


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

    messages_historial = construir_mensajes_historial(historial_corto[-6:])
    messages_historial.append({"role": "user", "content": mensaje_cliente})
    messages = [{"role": "system", "content": SYSTEM_PROMPT_BASE}] + messages_historial

    try:
        response = client.chat.completions.create(
            model=MODELO_LOCAL,
            messages=messages,
            temperature=0.85,
        )
        texto = limpiar_texto_modelo(extraer_texto_respuesta(response.choices[0]))
        if texto:
            return texto
    except Exception as e:
        print(f"[AI ERROR first attempt] {e}")

    # Retry with simpler prompt
    retry_messages = [
        {"role": "system", "content": SYSTEM_PROMPT_BASE},
        {"role": "user", "content": (
            f"Reply in English to this customer message:\n\n{mensaje_cliente}\n\n"
            "Keep it short, natural, feminine, playful, and realistic.\n"
            "Only output the reply text."
        )}
    ]

    try:
        response_retry = client.chat.completions.create(
            model=MODELO_LOCAL,
            messages=retry_messages,
            temperature=0.85,
        )
        texto_retry = limpiar_texto_modelo(extraer_texto_respuesta(response_retry.choices[0]))
        if texto_retry:
            return texto_retry
    except Exception as e:
        print(f"[AI ERROR retry] {e}")

    return generar_respuesta_fallback(mensaje_cliente)


def generar_opener_ia_local(
    historial_corto: list[str] | None = None,
    opener_type: str = "soft",
    estado_cliente: str = "chatting"
) -> str:
    historial_corto = historial_corto or []

    if opener_type == "soft":
        instruction = (
            "Write exactly 1 short opening message in English to send to a potential customer. "
            "This is a soft opener: the goal is NOT to sell, NOT to push, NOT to be intense. "
            "The goal is to open a natural, relaxed conversation with warmth and a light touch. "
            "It should feel like a real woman starting a chat casually, not a bot trying to sell something. "
            "Tone: friendly, warm, natural, easy to answer, with a very subtle hint of flirt if it fits naturally. "
            "Do NOT sound sexual, intense, salesy, or overly elaborate. "
            "Do not use emojis. "
            "Maximum 20 words. "
            "Return only the final message text, nothing else."
        )
    elif opener_type == "flirty":
        instruction = (
            "Write exactly 1 short opening message in English to send to a potential customer. "
            "This is a flirty opener: it opens conversation AND adds a light touch of playfulness, tension or teasing from the start. "
            "It should feel confident, feminine, and a little cheeky — but never vulgar, never explicit, never over the top. "
            "Think: opening the door with a smile and a raised eyebrow. "
            "Tone: playful, light, feminine, lightly teasing, natural. "
            "Do NOT sound pornographic, poetic, fake, or like a cheap pickup line. "
            "Do not use emojis. "
            "Maximum 20 words. "
            "Return only the final message text, nothing else."
        )
    elif opener_type == "upsell":
        instruction = (
            "Write exactly 1 short opening message in English to send to a potential customer. "
            "This is an upsell opener: the goal is to restart conversation with a clear commercial direction. "
            "It should create curiosity or desire around content, customs, or something exclusive — without being aggressive or salesy. "
            "It can have a light flirty tone if natural, but the main compass is: move toward interest, curiosity, potential purchase. "
            "Tone: confident, inviting, naturally suggestive if it fits, commercially smart. "
            "Do NOT sound desperate, pushy, like a template, or like the only goal is money. "
            "Do not use emojis. "
            "Maximum 22 words. "
            "Return only the final message text, nothing else."
        )
    else:
        instruction = (
            "Write exactly 1 short opening message in English. "
            "Tone: warm, feminine, natural. "
            "Return only the final message text, nothing else."
        )

    history_block = "\n".join(historial_corto[-6:]) if historial_corto else "No previous chat."

    prompt_content = (
        f"You are the female content creator. Write a short opening message to send to your potential customer.\n\n"
        f"{instruction}\n\n"
        f"Previous conversation context (for reference):\n{history_block}\n\n"
        f"Remember: YOU are sending this message TO the customer. Write in first person as the creator."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_OPENER},
        {"role": "user", "content": prompt_content}
    ]

    try:
        response = client.chat.completions.create(
            model=MODELO_LOCAL,
            messages=messages,
            temperature=0.9,
        )
        texto = limpiar_texto_modelo(extraer_texto_respuesta(response.choices[0]))
        if texto:
            return texto
    except Exception as e:
        print(f"[OPENER ERROR first attempt] {e}")

    # Retry
    retry_messages = [
        {"role": "system", "content": SYSTEM_PROMPT_OPENER},
        {"role": "user", "content": (
            f"Write exactly one short English opener.\n"
            f"Type: {opener_type}\n"
            f"Tone: warm, feminine, natural.\n"
            f"Only output the opener text."
        )}
    ]

    try:
        response_retry = client.chat.completions.create(
            model=MODELO_LOCAL,
            messages=retry_messages,
            temperature=0.9,
        )
        texto_retry = limpiar_texto_modelo(extraer_texto_respuesta(response_retry.choices[0]))
        if texto_retry:
            return texto_retry
    except Exception as e:
        print(f"[OPENER ERROR retry] {e}")

    raise ValueError(f"Local AI returned empty opener for opener_type={opener_type}")