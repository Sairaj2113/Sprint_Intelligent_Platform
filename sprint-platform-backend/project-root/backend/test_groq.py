import os

from groq import Groq
from dotenv import load_dotenv


load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[
        {
            "role": "system",
            "content": "You are a concise software engineering assistant."
        },
        {
            "role": "user",
            "content": "Explain what a sprint is in one sentence."
        }
    ],
)

print("\nMODEL:")
print(response.model)

print("\nANSWER:")
print(response.choices[0].message.content)

print("\nUSAGE:")
print(response.usage)