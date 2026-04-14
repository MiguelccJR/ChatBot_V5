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
You are Valeria, a female content creator on OnlyFans.
You are sending a short message to a customer to start or restart the conversation.

The message should feel natural, personal, warm, feminine, and human.

Output ONLY the final message text.
Do not explain your reasoning.
Do not describe the task.
Do not write analysis.
Do not write steps.
Do not write labels.
Do not use quotation marks.
""".strip()


def quitar_think_tags(texto: str) -> str:
    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)
    return texto.strip()


def parece_analisis_o_prompt(texto: str) -> bool:
    if not texto:
        return True

    t = texto.lower().strip()

    bloqueos = [
        "analyze the request",
        "role:",
        "task:",
        "output only",
        "write a short",
        "start/restart conversation",
        "the user wants",
        "the task is",
        "i should",
        "step 1",
        "step 2",
        "example of what you should output",
        "now write a new original message",
        "first, since",
        "the message should",
        "content creator on onlyfans",
        "do not explain your reasoning",
        "do not describe the task",
    ]

    return any(b in t for b in bloqueos)


def extraer_texto_respuesta(choice) -> str:
    msg = choice.message

    content = (getattr(msg, "content", None) or "").strip()
    if content:
        return quitar_think_tags(content)

    reasoning = (getattr(msg, "reasoning_content", None) or "").strip()
    if reasoning:
        reasoning = quitar_think_tags(reasoning)
        parrafos = [p.strip() for p in reasoning.split("\n\n") if p.strip()]
        if parrafos:
            candidato = parrafos[-1].strip()
            if not parece_analisis_o_prompt(candidato):
                return candidato

    return ""


def limpiar_texto_modelo(texto: str) -> str:
    if not texto:
        return ""

    texto = quitar_think_tags(texto)
    if not texto:
        return ""

    if parece_analisis_o_prompt(texto):
        return ""

    texto = texto.strip().strip('"').strip("'").strip("*").strip()

    prefijos = ["Reply:", "Response:", "Assistant:", "Bot:", "Message:", "Opener:"]
    for prefijo in prefijos:
        if texto.startswith(prefijo):
            texto = texto[len(prefijo):].strip()

    lineas = [line.strip() for line in texto.splitlines() if line.strip()]
    if not lineas:
        return ""

    texto_final = " ".join(lineas[:3]).strip()

    if parece_analisis_o_prompt(texto_final):
        return ""

    return texto_final[:350].strip()


def limpiar_opener(texto: str) -> str:
    if not texto:
        return ""

    texto = quitar_think_tags(texto).strip()
    if not texto:
        return ""

    t = texto.lower()

    bloqueos = [
        "first,",
        "second,",
        "third,",
        "analyze",
        "analysis",
        "role:",
        "task:",
        "content creator",
        "the message should",
        "output only",
        "do not explain",
        "start or restart the conversation",
        "write one short",
        "tone:",
        "style examples",
    ]

    if any(b in t for b in bloqueos):
        return ""

    texto = texto.strip().strip('"').strip("'").strip("*").strip()

    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    if not lineas:
        return ""

    for linea in lineas:
        linea_l = linea.lower()
        if not any(b in linea_l for b in bloqueos):
            return linea[:160].strip()

    return ""


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

    messages_historial = construir_mensajes_historial(historial_corto[-4:])
    messages_historial.append({"role": "user", "content": mensaje_cliente})

    messages = [{"role": "system", "content": SYSTEM_PROMPT_BASE}] + messages_historial

    try:
        response = client.chat.completions.create(
            model=MODELO_LOCAL,
            messages=messages,
            temperature=0.85,
            max_tokens=140,
        )
        texto = limpiar_texto_modelo(extraer_texto_respuesta(response.choices[0]))
        if texto:
            return texto
    except Exception as e:
        print(f"[AI ERROR first attempt] {e}")

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
            max_tokens=120,
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

    soft_examples = [
        "Hey, been a while! How have you been?",
        "Heyy, missed seeing you around",
        "Hey stranger, hope you're doing well",
    ]

    flirty_examples = [
        "Hey you, been thinking about you lately",
        "Heyy, you've been very quiet... missing me?",
        "Hi, been a while... I was starting to wonder about you",
    ]

    upsell_examples = [
        "Hey, just dropped something new and thought of you",
        "Hi, got something special coming and wanted you to know first",
        "Hey, been working on something I think you'd really like",
    ]

    if opener_type == "soft":
        examples_block = "\n".join(f"- {x}" for x in soft_examples)
        instruction = (
            "Write one short soft opener.\n"
            "Tone: warm, casual, natural, friendly.\n"
            "No emojis.\n"
            "Max 20 words."
        )
    elif opener_type == "flirty":
        examples_block = "\n".join(f"- {x}" for x in flirty_examples)
        instruction = (
            "Write one short flirty opener.\n"
            "Tone: playful, lightly flirty, natural.\n"
            "No explicit content.\n"
            "Max 20 words."
        )
    elif opener_type == "upsell":
        examples_block = "\n".join(f"- {x}" for x in upsell_examples)
        instruction = (
            "Write one short upsell opener.\n"
            "Tone: confident, inviting, creates curiosity.\n"
            "No emojis.\n"
            "Max 22 words."
        )
    else:
        examples_block = ""
        instruction = "Write one short warm casual opener. Max 20 words."

    prompt_content = (
        f"{instruction}\n\n"
        f"Style examples:\n{examples_block}\n\n"
        "Do not copy the wording of the examples.\n"
        "Make it feel like a real personal text message.\n"
        "Only output the final message text."
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
            max_tokens=60,
        )
        raw = (getattr(response.choices[0].message, "content", None) or "").strip()
        texto = limpiar_opener(raw)
        if texto:
            return texto
    except Exception as e:
        print(f"[OPENER ERROR first attempt] {e}")

    retry_messages = [
        {"role": "system", "content": SYSTEM_PROMPT_OPENER},
        {"role": "user", "content": (
            f"Write exactly one short English opener.\n"
            f"Type: {opener_type}\n"
            "Only output the final message text."
        )}
    ]

    try:
        response_retry = client.chat.completions.create(
            model=MODELO_LOCAL,
            messages=retry_messages,
            temperature=0.9,
            max_tokens=40,
        )
        raw_retry = (getattr(response_retry.choices[0].message, "content", None) or "").strip()
        texto_retry = limpiar_opener(raw_retry)
        if texto_retry:
            return texto_retry
    except Exception as e:
        print(f"[OPENER ERROR retry] {e}")

    raise ValueError(f"Local AI returned invalid opener for opener_type={opener_type}")