"""
Cerberus Text-to-Speech (TTS) Service v3.0 - Jarvis Edition (Optimized for Mark/David)
Optimized for limited Windows voices with enhanced SSML processing
"""
import asyncio
import nats
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
import json
import re

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JarvisVoice:
    """
    Enhanced Windows SAPI5 voice optimized for Mark/David voices.
    """
    def __init__(self):
        # Mark is deeper than David, so prefer it
        self.voice_name = "Microsoft Mark Desktop"
        self.fallback_voice = "Microsoft David Desktop"
        
        # Optimized settings for Mark/David to sound like Jarvis
        self.rate = -3          # Slower speech (Mark sounds better slower)
        self.volume = 100       # Max volume
        self.pitch = "-25%"     # Maximum pitch reduction for deepest voice
        
        # Check if Mark is actually available
        self.verify_voice()
        
    def verify_voice(self):
        """Verify Mark is available, fallback to David if not."""
        logger.info("Verifying voice availability...")
        
        script = """
        Add-Type -AssemblyName System.Speech
        $sp = New-Object System.Speech.Synthesis.SpeechSynthesizer
        $voices = $sp.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }
        $voices -join ','
        """
        
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                check=True
            )
            
            available_voices = result.stdout.strip().split(',')
            logger.info(f"Available voices: {available_voices}")
            
            # Check if Mark is available
            if not any("Mark" in voice for voice in available_voices):
                logger.warning("Mark not found, using David")
                self.voice_name = self.fallback_voice
                # David needs slightly different settings
                self.pitch = "-20%"  # David can't go as low as Mark
                self.rate = -2
            else:
                logger.info("✅ Mark voice confirmed")
                
        except Exception as e:
            logger.error(f"Failed to verify voices: {e}")
            self.voice_name = self.fallback_voice

    def create_jarvis_ssml(self, text: str) -> str:
        """
        Create highly optimized SSML for Jarvis-like speech with Mark/David.
        """
        # Add more sophisticated preprocessing
        # 1. Add pauses for natural speech rhythm
        text = re.sub(r'\. ', '. <break time="500ms"/>', text)
        text = re.sub(r', ', ', <break time="250ms"/>', text)
        text = re.sub(r'\? ', '? <break time="500ms"/>', text)
        text = re.sub(r'! ', '! <break time="400ms"/>', text)
        
        # 2. Add pauses around "sir" for that butler-like effect
        text = re.sub(r'\b(sir|Sir)\b', '<break time="150ms"/>\\1<break time="300ms"/>', text)
        
        # 3. Emphasize technical/important words
        tech_words = [
            'initialized', 'system', 'online', 'offline', 'activated', 'deactivated',
            'complete', 'error', 'warning', 'critical', 'analysis', 'processing',
            'confirmed', 'detected', 'scanning', 'diagnostic', 'operational'
        ]
        
        for word in tech_words:
            text = re.sub(
                rf'\b({word})\b', 
                rf'<emphasis level="strong"><prosody rate="90%">\1</prosody></emphasis>', 
                text, 
                flags=re.IGNORECASE
            )
        
        # 4. Slow down numbers for clarity
        text = re.sub(r'\b(\d+)\b', r'<prosody rate="80%">\1</prosody>', text)
        
        # Build the SSML with maximum voice modification
        if self.voice_name == "Microsoft Mark Desktop":
            # Mark-specific optimizations
            ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
                <voice name="{self.voice_name}">
                    <prosody pitch="{self.pitch}" rate="75%" volume="100">
                        <prosody contour="(0%,-2Hz) (50%,-5Hz) (100%,-2Hz)">
                            {text}
                        </prosody>
                    </prosody>
                </voice>
            </speak>"""
        else:
            # David-specific optimizations (can't go as deep)
            ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
                <voice name="{self.voice_name}">
                    <prosody pitch="-20%" rate="80%" volume="100">
                        {text}
                    </prosody>
                </voice>
            </speak>"""
            
        return ssml

    def speak(self, text: str):
        """
        Enhanced speak method with better error handling and SSML processing.
        """
        logger.info(f"Speaking: '{text}'")
        
        try:
            # Create SSML
            ssml = self.create_jarvis_ssml(text)
            
            # Clean SSML for PowerShell
            ssml_escaped = ssml.replace('"', '`"').replace('\n', ' ').replace('\r', '')
            
            # Enhanced PowerShell script with audio tweaks
            script = f"""
            Add-Type -AssemblyName System.Speech
            $sp = New-Object System.Speech.Synthesis.SpeechSynthesizer
            
            # Set audio output to best quality
            $sp.SetOutputToDefaultAudioDevice()
            
            # Force voice selection
            try {{
                $sp.SelectVoice("{self.voice_name}")
            }} catch {{
                try {{
                    $sp.SelectVoice("{self.fallback_voice}")
                }} catch {{
                    Write-Host "Using system default voice"
                }}
            }}
            
            # Additional voice settings
            $sp.Rate = {self.rate}
            $sp.Volume = {self.volume}
            
            # Speak with SSML
            try {{
                $sp.SpeakSsml("{ssml_escaped}")
            }} catch {{
                # Fallback to plain text if SSML fails
                $sp.Speak("{text.replace('"', '`"')}")
            }}
            """
            
            # Execute with increased priority for smoother audio
            process = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                text=True,
                creationflags=subprocess.HIGH_PRIORITY_CLASS if hasattr(subprocess, 'HIGH_PRIORITY_CLASS') else 0
            )
            
            if process.stderr and "Warning" not in process.stderr:
                logger.error(f"PowerShell error: {process.stderr}")
                
        except Exception as e:
            logger.error(f"Speech failed: {e}")
            self._simple_speak_fallback(text)
    
    def _simple_speak_fallback(self, text: str):
        """Ultra-simple fallback without SSML."""
        try:
            script = f"""
            Add-Type -AssemblyName System.Speech
            $sp = New-Object System.Speech.Synthesis.SpeechSynthesizer
            $sp.Rate = {self.rate}
            $sp.Speak("{text.replace('"', '`"')}")
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", script])
        except:
            logger.error("Even fallback speech failed!")

class TTSService:
    def __init__(self):
        self.nc = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.voice = JarvisVoice()
        
        # Test the voice on startup
        self._test_voice()
        
    def _test_voice(self):
        """Test voice with a Jarvis-like greeting."""
        test_phrases = [
            "Voice system initialized.",
            "Good evening, sir. All systems are operational.",
            "Standing by for your commands."
        ]
        
        import random
        test_phrase = random.choice(test_phrases)
        
        try:
            logger.info("Testing voice system...")
            self.voice.speak(test_phrase)
            logger.info("✅ Jarvis TTS Service ready")
        except Exception as e:
            logger.error(f"Voice test failed: {e}")

    async def message_handler(self, msg):
        """Async handler for NATS messages."""
        try:
            # Try JSON format first
            data = json.loads(msg.data.decode())
            text_to_speak = data.get('text', '')
            
            # Support for different speech styles
            style = data.get('style', 'normal')
            if style == 'alert':
                text_to_speak = f"<emphasis level='strong'>Alert: </emphasis>{text_to_speak}"
            elif style == 'confirmation':
                text_to_speak = f"<prosody rate='90%'>{text_to_speak}</prosody>"
                
        except (json.JSONDecodeError, AttributeError):
            text_to_speak = msg.data.decode()
        
        logger.info(f"Received: '{text_to_speak}'")
        
        # Speak in executor
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.executor,
            self.voice.speak,
            text_to_speak
        )

    async def run(self):
        """Main service loop."""
        try:
            self.nc = await nats.connect("nats://localhost:4222")
            logger.info("✅ Connected to NATS")
            
            await self.nc.subscribe("agent.speak", cb=self.message_handler)
            logger.info("Subscribed to 'agent.speak'")
            
            await asyncio.Future()  # Keep running
        except Exception as e:
            logger.error(f"❌ Service error: {e}")
        finally:
            if self.nc:
                await self.nc.close()

if __name__ == "__main__":
    service = TTSService()
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("\nJarvis TTS Service stopped.")