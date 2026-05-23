import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Profil laden
with open("profil.txt", "r", encoding="utf-8") as f:
    profil = f.read()

# Stelle eingeben
with open("stelle.txt", "r", encoding="utf-8") as f:
    stelle = f.read()
print("Stelle geladen! Analysiere...")

message = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    system="Du bist ein erfahrener Karriere-Scout. Du bekommst ein Bewerberprofil und eine Stellenanzeige. Vergleiche beide und antworte NUR so:\nSCORE: [1-10]\nBEGRUENDUNG: [2-3 Sätze]\nSTAERKEN: [Was passt gut]\nLUECKEN: [Was fehlt]\nEMPFEHLUNG: [Bewerben oder Überspringen]",
    messages=[
        {"role": "user", "content": f"MEIN PROFIL:\n{profil}\n\nSTELLENANZEIGE:\n{stelle}"}
    ]
)

print("\n--- SCOUT BEWERTUNG ---")
print(message.content[0].text)