from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:1234/v1",
    api_key="lm-studio"
)

response = client.responses.create(
    model="qwen/qwen3.5-9b",
    instructions=(
        "You are chatting as a female content creator talking to a potential customer in English. "
        "Your tone is warm, feminine, playful, polite, and natural. "
        "Never say you are an AI or an assistant. "
        "Keep replies short and natural."
    ),
    input="Can i tip for something special?"
)

print(response.output_text)