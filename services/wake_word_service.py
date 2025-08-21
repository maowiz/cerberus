import asyncio
import nats
import pvporcupine
# import pvrhino  # <-- Temporarily disable this import
import pyaudio
import struct
from typing import Optional

class WakeWordService:
    def __init__(self):
        self.nc: Optional[nats.NATS] = None
        self.porcupine: Optional[pvporcupine.Porcupine] = None
        # self.rhino: Optional[pvrhino.Rhino] = None # <-- Temporarily disable this line
        self.audio_stream: Optional[pyaudio.Stream] = None
        self.pa: Optional[pyaudio.PyAudio] = None
        self.is_listening = False
        self.wake_word_detected = False
        
        # Audio configuration
        self.sample_rate = 16000
        self.frame_length = 512
        
    async def initialize(self):
        """Initialize all components"""
        try:
            # Connect to NATS
            self.nc = await nats.connect("nats://localhost:4222")
            print("✅ Wake Word Service connected to NATS")
            
            PICOVOICE_ACCESS_KEY = "ezjFqKiffcifM+ZNtU3ZbZ+ODmtcqon4yBFAWJ2aclLi9CmRmARE8g=="
            
            # Initialize Porcupine (Wake Word Detection)
            self.porcupine = pvporcupine.create(
                access_key=PICOVOICE_ACCESS_KEY,
                keywords=['hey google']
            )
            print("✅ Porcupine wake word engine initialized")
            
            # --- Temporarily Disabled Rhino Section ---
            # self.rhino = pvrhino.create(
            #     access_key=PICOVOICE_ACCESS_KEY,
            #     context_path=self._create_simple_context()
            # )
            # print("✅ Rhino speech-to-intent engine initialized")
            
            # Initialize audio
            self.pa = pyaudio.PyAudio()
            self.audio_stream = self.pa.open(
                rate=self.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.frame_length,
                input_device_index=None
            )
            print("✅ Audio stream initialized")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize Wake Word Service: {e}")
            return False
    
    def _create_simple_context(self):
        return None
    
    async def start_listening(self):
        """Start the main listening loop"""
        if not await self.initialize():
            return
            
        self.is_listening = True
        print("🎤 Wake Word Service is now listening...")
        print("💡 Say 'Hey Google' to activate the assistant")
        
        try:
            while self.is_listening:
                pcm = self.audio_stream.read(self.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.frame_length, pcm)
                
                if not self.wake_word_detected:
                    keyword_index = self.porcupine.process(pcm)
                    
                    if keyword_index >= 0:
                        print("🔥 WAKE WORD DETECTED!")
                        self.wake_word_detected = True
                        
                        await self.nc.publish("wake_word.detected", b"activated")
                        
                        print("🎯 Listening for your command...")
                        
                        asyncio.create_task(self._reset_wake_word_after_delay(5.0))
                
                else:
                    pass
                    
                await asyncio.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n🛑 Wake Word Service stopping...")
        except Exception as e:
            print(f"❌ Error in listening loop: {e}")
        finally:
            await self.cleanup()
    
    async def _reset_wake_word_after_delay(self, delay: float):
        """Reset wake word detection after a delay"""
        await asyncio.sleep(delay)
        if self.wake_word_detected:
            self.wake_word_detected = False
            print("⏰ Wake word session timed out. Listening for wake word again...")
    
    async def cleanup(self):
        """Clean up all resources"""
        self.is_listening = False
        
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            
        if self.pa:
            self.pa.terminate()
            
        if self.porcupine:
            self.porcupine.delete()
            
        # if self.rhino: # <-- Temporarily disable this
        #     self.rhino.delete()
            
        if self.nc:
            await self.nc.close()
            
        print("✅ Wake Word Service cleaned up")

async def run():
    """Main entry point for the service"""
    service = WakeWordService()
    await service.start_listening()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nWake Word Service stopped by user")