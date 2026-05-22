# ============================================================
# test_ws.py  —  Terminal WebSocket test client
# Run: python test_ws.py
# ============================================================

import asyncio
import json
import websockets


async def test_voice_agent():
    phone = "9876543210"   # Rahul Verma from seed data
    uri   = f"ws://localhost:8000/ws/voice/{phone}"

    print(f"\nConnecting to {uri} ...\n")

    async with websockets.connect(uri) as ws:
        # Welcome message
        resp = await ws.recv()
        print("SERVER:", json.loads(resp), "\n")

        # Test messages simulating voice conversations
        test_messages = [
            "Book appointment with cardiologist tomorrow",
            "I want to see a dermatologist",
            "Cancel my appointment",
            "मुझे कल डॉक्टर से मिलना है",
            "நாளை மருத்துவரை பார்க்க வேண்டும்",
        ]

        for text in test_messages:
            print(f"YOU  → {text}")
            await ws.send(json.dumps({"type": "text", "text": text}))
            resp = json.loads(await ws.recv())
            print(f"BOT  → {resp.get('text')}")
            print(f"LANG   {resp.get('language')} | "
                  f"intent={resp.get('intent')} | "
                  f"latency={resp.get('latency', {}).get('total_ms')}ms")
            print()
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(test_voice_agent())