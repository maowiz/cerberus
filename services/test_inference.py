import asyncio
import nats
import time

async def test_inference_service():
    """Test script to verify the inference service is working"""
    
    try:
        # Connect to NATS
        nc = await nats.connect("nats://localhost:4222")
        print("✅ Connected to NATS server")
        
        # Test prompt
        test_prompt = "Hello! Please introduce yourself in one sentence."
        print(f"📤 Sending test prompt: '{test_prompt}'")
        
        # Record start time for performance measurement
        start_time = time.time()
        
        # Send the prompt and wait for response (with 30 second timeout)
        try:
            response = await nc.request("llm.generate", test_prompt.encode(), timeout=30.0)
            end_time = time.time()
            
            # Decode and display the response
            llm_response = response.data.decode()
            response_time = end_time - start_time
            
            print(f"📥 LLM Response: {llm_response}")
            print(f"⏱️  Response time: {response_time:.2f} seconds")
            print("✅ Inference service test PASSED!")
            
        except asyncio.TimeoutError:
            print("❌ Test FAILED: Timeout waiting for response")
            print("   Make sure Ollama is running and the model is loaded")
            
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        print("   Make sure NATS server is running")
    
    finally:
        if 'nc' in locals():
            await nc.close()

if __name__ == "__main__":
    print("🧪 Testing Inference Service...")
    print("=" * 50)
    asyncio.run(test_inference_service())