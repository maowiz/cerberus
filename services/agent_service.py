"""
Cerberus Agent Service
This service is the core cognitive loop of the assistant.
It listens for commands, thinks using an LLM, and decides what to do.
"""
import asyncio
import nats
import json
import logging

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self):
        self.nc = None

    async def message_handler(self, msg):
        """Handles incoming parsed commands from the STT service."""
        subject = msg.subject
        data = json.loads(msg.data.decode())
        
        command = data.get("command")
        params = data.get("parameters")
        logger.info(f"Received parsed command: {command} with params: {params}")

        # --- Step 1: Think ---
        # Formulate a prompt for the LLM to generate a response.
        # For now, we're just confirming the action. Later, this is where
        # the agent would decide to call other tools (e.g., OS management).
        prompt = f"You are Cerberus, a helpful AI assistant. A user has given the command '{command}' with the parameters '{params}'. Formulate a brief, natural language response confirming you have received and understood the command. For example, for 'open_my_computer', you could say 'Opening This PC now.'."

        try:
            # --- Step 2: Act (by asking the LLM) ---
            # Send the prompt to the Inference Service and wait for a response.
            response_msg = await self.nc.request("llm.generate", prompt.encode(), timeout=30.0)
            llm_response = response_msg.data.decode()
            logger.info(f"LLM formulated response: '{llm_response}'")

            # --- Step 3: Respond ---
            # Send the LLM's response to the TTS Service to be spoken.
            await self.nc.publish("agent.speak", llm_response.encode())

        except asyncio.TimeoutError:
            logger.error("Request to Inference Service timed out.")
            # Optionally, speak an error message
            await self.nc.publish("agent.speak", "Sorry, my brain is a little slow right now.".encode())
        except Exception as e:
            logger.error(f"An error occurred in the agent: {e}")


    async def run(self):
        """Main entry point and loop for the service."""
        try:
            self.nc = await nats.connect("nats://localhost:4222")
            logger.info("✅ Agent Service connected to NATS")
            
            # This service listens for the structured commands from the STT
            await self.nc.subscribe("stt.command.parsed", cb=self.message_handler)
            logger.info("Subscribed to 'stt.command.parsed'")
            
            await asyncio.Future()
        except Exception as e:
            logger.error(f"❌ Critical error in Agent service: {e}")
        finally:
            if self.nc:
                await self.nc.close()

if __name__ == "__main__":
    service = AgentService()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("\nAgent Service stopped by user.")