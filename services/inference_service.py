import asyncio
import nats
import json
import aiohttp

# Configuration for the Ollama service
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.1:8b-instruct-q4_K_M"

async def run():
    # Connect to the NATS server
    nc = await nats.connect("nats://localhost:4222")
    print("Inference Service connected to NATS")

    # Create a reusable session for making HTTP requests
    async with aiohttp.ClientSession() as session:

        # Define the message handler that will process incoming prompts
        async def message_handler(msg):
            prompt = msg.data.decode()
            print(f"Received prompt: '{prompt[:50]}...'")

            # Prepare the data payload for the Ollama API
            payload = {
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False # We want the full response, not a stream
            }

            try:
                # Send the request to the Ollama API
                async with session.post(OLLAMA_API_URL, json=payload) as response:
                    if response.status == 200:
                        # Get the full response JSON
                        response_data = await response.json()
                        final_response = response_data.get("response", "").strip()

                        print(f"LLM Response: '{final_response[:50]}...'")

                        # Publish the final response to a dedicated subject
                        # We'll use msg.reply to send it back to the requester
                        await nc.publish(msg.reply, final_response.encode())
                    else:
                        error_text = await response.text()
                        print(f"Error from Ollama API: {response.status} - {error_text}")
                        await nc.publish(msg.reply, f"Error: Could not get a response from Ollama.".encode())

            except aiohttp.ClientConnectorError:
                print("Error: Could not connect to Ollama. Is it running?")
                await nc.publish(msg.reply, "Error: Ollama connection failed.".encode())
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                await nc.publish(msg.reply, f"Error: An internal error occurred.".encode())

        # Subscribe to the subject where prompts will be sent
        await nc.subscribe("llm.generate", cb=message_handler)
        print("Subscribed to 'llm.generate'")

        # Keep the service running indefinitely
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nInference Service stopped")