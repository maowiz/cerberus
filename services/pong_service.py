import asyncio
import nats

async def run():
    # Connect to NATS
    nc = await nats.connect("nats://localhost:4222")
    print("Pong Service connected to NATS")

    # Define a message handler
    async def message_handler(msg):
        subject = msg.subject
        data = msg.data.decode()
        print(f"Received a message on '{subject}': {data}")

    # Subscribe to the 'system.ping' subject
    await nc.subscribe("system.ping", cb=message_handler)
    print("Subscribed to 'system.ping'")

    # Keep the service running
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        await nc.close()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nPong Service stopped")