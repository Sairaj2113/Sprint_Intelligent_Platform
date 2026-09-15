import os

from dotenv import load_dotenv
from google import genai


load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="Explain what a sprint is in one sentence.",
    store=False,
)

print("\nMODEL:")
print(interaction.model)

print("\nANSWER:")
print(interaction.output_text)

print("\nUSAGE:")
print(interaction.usage)