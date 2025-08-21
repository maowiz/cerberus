import asyncio
import nats
import time

async def run():
    # Connect to NATS
    nc = await nats.connect("nats://localhost:4222")
    print("Ping Service connected to NATS")
    
    # Send ping every 2 seconds
    while True:
        msg = f"ping - {time.time()}"
        await nc.publish("system.ping", msg.encode())
        print(f"Sent: {msg}")
        await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Ping Service stopped")