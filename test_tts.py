# test_tts.py
import asyncio
import nats

async def run_test():
    try:
        nc = await nats.connect("nats://localhost:4222")
        print("Connected to NATS, sending test message...")

        test_message = "Hello, this is the Cerberus assistant. My voice is now online. i love you maowiz "
        await nc.publish("agent.speak", test_message.encode())
        print(f"Sent message: '{test_message}'")

        await nc.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())