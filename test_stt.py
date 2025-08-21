import asyncio
import nats
import json

async def run_test():
    """Connects to NATS and listens for STT results."""
    try:
        nc = await nats.connect("nats://localhost:4222")
        print("Connected to NATS, listening for STT messages...")

        async def command_handler(msg):
            subject = msg.subject
            data = json.loads(msg.data.decode())
            print(f"\n--- Parsed Command ---\n"
                  f"Timestamp: {data.get('timestamp')}\n"
                  f"Engine: {data.get('engine', 'offline')}\n"
                  f"Command: {data.get('command')}\n"
                  f"Category: {data.get('category')}\n"
                  f"Parameters: {data.get('parameters')}\n"
                  f"Original Text: '{data.get('original_text')}'\n"
                  f"----------------------")

        async def transcription_handler(msg):
            subject = msg.subject
            data = json.loads(msg.data.decode())
            print(f"\n--- Online Transcription ---\n"
                  f"Timestamp: {data.get('timestamp')}\n"
                  f"Engine: {data.get('engine')}\n"
                  f"Text: '{data.get('text')}'\n"
                  f"--------------------------")

        # Subscribe to both parsed commands (offline) and raw transcriptions (online)
        await nc.subscribe("stt.command.parsed", cb=command_handler)
        await nc.subscribe("stt.transcription.online", cb=transcription_handler)

        # Keep the script running to listen for messages
        await asyncio.Future()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\nListener stopped.")
