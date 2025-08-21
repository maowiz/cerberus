import asyncio
import nats

async def test_wake_word_service():
    """Test script to monitor wake word detections"""
    
    try:
        # Connect to NATS
        nc = await nats.connect("nats://localhost:4222")
        print("✅ Connected to NATS server")
        print("🎤 Monitoring for wake word detections...")
        print("💡 Start the wake word service and say 'Hey Google'")
        print("=" * 50)
        
        # Handler for wake word detection messages
        async def wake_word_handler(msg):
            print("🔥 WAKE WORD DETECTED! The system is now active!")
            print("   (In the full system, this would trigger STT)")
        
        # Subscribe to wake word detection messages
        await nc.subscribe("wake_word.detected", cb=wake_word_handler)
        
        # Keep listening
        await asyncio.Future()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        if 'nc' in locals():
            await nc.close()

if __name__ == "__main__":
    try:
        asyncio.run(test_wake_word_service())
    except KeyboardInterrupt:
        print("\n🛑 Wake word test stopped")