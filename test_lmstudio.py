from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:1234",
    api_key="lm-studio"
)

response = client.chat.completions.create(
    model="qwen/qwen3.5-9b",
    messages=[
        {
            "role": "system",
            "content": (
                "You are chatting as a female content creator talking to a potential customer in English. "
                "Your tone is warm, feminine, playful, polite, and natural. "
                "Never say you are an AI or an assistant. "
                "Keep replies short and natural."
            )
        },
        {
            "role": "user",
            "content": "Can i tip for something special?"
        }
    ],
    temperature=0.7
)

print(response.choices[0].message.content)