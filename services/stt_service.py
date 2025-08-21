"""
Cerberus STT Service - Hybrid Speech-to-Text with Online/Offline modes
Clean architecture with proper async/sync separation
"""

import asyncio
import nats
import json
import time
import threading
import queue
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import socket
import os
import subprocess
import platform
import requests
import websocket
import pyaudio
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import atexit
from concurrent.futures import ThreadPoolExecutor
import speech_recognition as sr

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class STTConfig:
    """Configuration for the STT Engine"""
    # Offline settings
    model_name: str = "base.en"
    wake_word: str = "jarvis"
    sample_rate: int = 16000
    chunk_duration_seconds: float = 3.0
    silence_threshold: float = 0.02
    cpu_threads: int = 4
    compute_type: str = "int8"
    command_timeout_seconds: int = 10
    
    # Online settings
    assemblyai_key: str = "d1978ba4b5274e24a85c02ca5eed1502"  # Replace with actual key
    flask_port: int = 5000

class GBNFCommandParser:
    """
    Parses transcribed text against a strict set of commands
    Full implementation from JARVIS
    """
    def __init__(self):
        self.commands = {
            'system': {
                'open_my_computer': {'patterns': [r'open\s+my\s+computer', r'open\s+this\s+pc'], 'params': []},
                'go_back': {'patterns': [r'go\s+back', r'back'], 'params': []},
                'close_current_window': {'patterns': [r'close\s+current\s+window', r'close\s+this\s+window'], 'params': []},
                'minimize_window': {'patterns': [r'minimize\s+window', r'minimize'], 'params': []},
                'maximize_window': {'patterns': [r'maximize\s+window', r'maximize'], 'params': []},
                'show_desktop': {'patterns': [r'show\s+desktop', r'minimize\s+all'], 'params': []},
                'lock_computer': {'patterns': [r'lock\s+computer', r'lock\s+screen'], 'params': []},
                'shutdown': {'patterns': [r'shutdown\s+computer', r'turn\s+off\s+computer'], 'params': []},
                'restart': {'patterns': [r'restart\s+computer', r'reboot'], 'params': []},
            },
            'window': {
                'close_window': {'patterns': [r'close\s+window', r'close\s+app'], 'params': []},
                'switch_window': {'patterns': [r'switch\s+window', r'next\s+window'], 'params': []},
                'task_view': {'patterns': [r'task\s+view', r'show\s+all\s+windows'], 'params': []},
                'snap_left': {'patterns': [r'snap\s+left', r'window\s+left'], 'params': []},
                'snap_right': {'patterns': [r'snap\s+right', r'window\s+right'], 'params': []},
            },
            'grid': {
                'show_grid': {'patterns': [r'show\s+grid', r'show\s+grade'], 'params': []},
                'hide_grid': {'patterns': [r'hide\s+grid', r'close\s+grid'], 'params': []},
                'click_cell': {'patterns': [r'click\s+cell\s+(\d+)', r'click\s+(\d+)'], 'params': ['cell_number']},
            },
            'application': {
                'open_app': {'patterns': [r'open\s+(.+)', r'launch\s+(.+)', r'start\s+(.+)'], 'params': ['app_name']},
                'close_app': {'patterns': [r'close\s+(.+)', r'quit\s+(.+)', r'exit\s+(.+)'], 'params': ['app_name']},
            },
            'navigation': {
                'scroll_up': {'patterns': [r'scroll\s+up', r'page\s+up'], 'params': []},
                'scroll_down': {'patterns': [r'scroll\s+down', r'page\s+down'], 'params': []},
                'click': {'patterns': [r'click', r'left\s+click'], 'params': []},
                'double_click': {'patterns': [r'double\s+click'], 'params': []},
                'right_click': {'patterns': [r'right\s+click'], 'params': []},
                'copy': {'patterns': [r'copy', r'ctrl\s+c'], 'params': []},
                'paste': {'patterns': [r'paste', r'ctrl\s+v'], 'params': []},
            },
            'media': {
                'volume_up': {'patterns': [r'volume\s+up', r'increase\s+volume'], 'params': []},
                'volume_down': {'patterns': [r'volume\s+down', r'decrease\s+volume'], 'params': []},
                'mute': {'patterns': [r'mute', r'mute\s+volume'], 'params': []},
                'play_pause': {'patterns': [r'play\s+pause', r'play', r'pause'], 'params': []},
            }
        }
        
        self.number_words = {
            'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
            'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10'
        }

    def _preprocess_text(self, text: str) -> str:
        text_lower = text.lower().strip()
        for word, digit in self.number_words.items():
            text_lower = re.sub(rf'\b{word}\b', digit, text_lower)
        return text_lower

    def parse_command(self, text: str) -> Optional[Dict]:
        processed_text = self._preprocess_text(text)
        
        for category, commands in self.commands.items():
            for cmd_name, cmd_info in commands.items():
                for pattern in cmd_info['patterns']:
                    match = re.search(pattern, processed_text)
                    if match:
                        params = dict(zip(cmd_info['params'], match.groups()))
                        return {
                            'category': category,
                            'command': cmd_name,
                            'original_text': text,
                            'parameters': params,
                            'timestamp': time.time()
                        }
        return None

    def generate_command_prompt(self) -> str:
        prompt_phrases = ["open", "close", "click", "scroll", "copy", "paste", 
                         "volume", "play", "pause", "minimize", "maximize"]
        return ", ".join(prompt_phrases) + "."

class OfflineSTTEngine:
    """Handles offline STT using Faster-Whisper"""
    
    def __init__(self, config: STTConfig, parser: GBNFCommandParser, result_queue: queue.Queue):
        self.config = config
        self.parser = parser
        self.result_queue = result_queue
        self.command_prompt = parser.generate_command_prompt()
        
        self.model = None
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.worker_thread = None
        
    def load_model(self):
        """Load Whisper model"""
        if not self.model:
            logger.info(f"Loading Whisper model: {self.config.model_name}")
            self.model = WhisperModel(
                self.config.model_name,
                device="cpu",
                compute_type=self.config.compute_type,
                cpu_threads=self.config.cpu_threads
            )
            logger.info("Whisper model loaded")
    
    def audio_callback(self, indata, frames, time_info, status):
        """Callback for audio stream"""
        if status:
            logger.warning(f"Audio status: {status}")
        if self.is_running:
            self.audio_queue.put(indata[:, 0].copy())
    
    def process_audio(self):
        """Process audio chunks"""
        audio_buffer = []
        
        while self.is_running:
            try:
                chunk = self.audio_queue.get(timeout=1.0)
                audio_buffer.append(chunk)
                
                buffer_duration = sum(len(c) for c in audio_buffer) / self.config.sample_rate
                if buffer_duration < self.config.chunk_duration_seconds:
                    continue
                
                full_audio = np.concatenate(audio_buffer)
                audio_buffer = []
                
                # Transcribe with command prompting
                segments, _ = self.model.transcribe(
                    full_audio,
                    beam_size=1,
                    temperature=0,
                    vad_filter=True,
                    language="en",
                    initial_prompt=self.command_prompt
                )
                
                text = " ".join(seg.text.strip() for seg in segments)
                
                if text:
                    logger.info(f"[OFFLINE] Transcribed: {text}")
                    # Always-on: try to parse into a command and emit if valid
                    command = self.parser.parse_command(text)
                    if command:
                        self.result_queue.put({'engine': 'offline', 'data': command})
                    
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Offline processing error: {e}")

    

    def run(self):
        """Main worker loop - runs in its own thread"""
        # Load model first
        self.load_model()
        self.is_running = True
        
        # Start audio processing thread
        process_thread = threading.Thread(target=self.process_audio, daemon=True)
        process_thread.start()
        
        # Start and manage audio stream HERE, not in start()
        with sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=1,
            dtype=np.float32,
            callback=self.audio_callback
        ) as stream:
            logger.info("[OFFLINE] Started listening")
            
            # Keep the thread alive while running
            while self.is_running:
                time.sleep(0.1)
        
        logger.info("[OFFLINE] Stopped")

    def stop(self):
        """Signal the worker to stop"""
        self.is_running = False

class OnlineSTTEngine:
    """
    Completely headless STT system.
    Primary: AssemblyAI (fast, accurate, needs key)
    Fallback: Google Speech Recognition (free, no key needed)
    """
    
    def __init__(self, config: STTConfig, result_queue: queue.Queue):
        self.config = config
        self.result_queue = result_queue
        self.is_running = False
        self.current_engine = None
        self.ws = None

        # Prefer AssemblyAI if a valid key is available, otherwise fall back to Google
        placeholder_keys = {
            None,
            "",
            "YOUR_ASSEMBLYAI_KEY_HERE",
            "d1978ba4b5274e24a85c02ca5eed1502",
            "Yd1978ba4b5274e24a85c02ca5eed1502",
        }
        # Allow providing the key via environment variable ASSEMBLYAI_KEY
        env_key = os.getenv("ASSEMBLYAI_KEY")
        effective_key = self.config.assemblyai_key or env_key
        if effective_key in placeholder_keys and env_key not in placeholder_keys:
            effective_key = env_key

        if effective_key in placeholder_keys:
            logger.warning("AssemblyAI key not set. Using Google Speech Recognition as the primary online engine.")
            self._start_google_recognition()
        else:
            # Normalize the config to use the effective key
            if self.config.assemblyai_key != effective_key:
                logger.info("Using ASSEMBLYAI_KEY from environment.")
                self.config.assemblyai_key = effective_key
            self._start_assemblyai_streaming()
        
        logger.info("✅ Pure Voice STT initialized - Running in background")
    
    def _start_assemblyai_streaming(self):
        self.current_engine = "assemblyai"
        logger.info("Starting AssemblyAI streaming engine...")
        
        FRAMES_PER_BUFFER = 3200
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        def connect_assemblyai():
            try:
                response = requests.post('https://api.assemblyai.com/v2/realtime/token', headers={'authorization': self.config.assemblyai_key}, json={'expires_in': 3600})
                if 'token' not in response.json():
                    raise KeyError("'token' not in response from AssemblyAI. Check your API key.")
                token = response.json()['token']
                ws_url = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate={RATE}&token={token}"
                
                def on_message(ws, message):
                    msg = json.loads(message)
                    if msg.get('message_type') == 'FinalTranscript':
                        text = msg.get('text', '').strip().lower()
                        if text:
                            self.result_queue.put({
                                'text': text,
                                'engine': 'online',
                                'timestamp': time.time()
                            })
                
                def on_error(ws, error): 
                    logger.error(f"AssemblyAI error: {error}")
                    # Fall back to Google if AssemblyAI errors out
                    if self.current_engine != "google":
                        self._start_google_recognition()
                
                def on_close(ws, _, __): 
                    logger.info("AssemblyAI connection closed")
                    # Only attempt to reconnect if AssemblyAI is still the desired engine
                    if self.is_running and self.current_engine == "assemblyai":
                        time.sleep(2)
                        connect_assemblyai()
                
                def on_open(ws):
                    logger.info("✅ AssemblyAI connected - Listening...")
                    def stream_audio():
                        p, stream = pyaudio.PyAudio(), None
                        try:
                            stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=FRAMES_PER_BUFFER)
                            while self.is_running and self.current_engine == "assemblyai":
                                ws.send(stream.read(FRAMES_PER_BUFFER, exception_on_overflow=False), websocket.ABNF.OPCODE_BINARY)
                        finally:
                            if stream: stream.close()
                            p.terminate()
                    threading.Thread(target=stream_audio, daemon=True).start()
                
                self.ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open)
                threading.Thread(target=self.ws.run_forever, daemon=True).start()
            except Exception as e: 
                logger.error(f"Failed to connect AssemblyAI: {e}")
                self._start_google_recognition()
        
        connect_assemblyai()
    
    def _start_google_recognition(self):
        self.current_engine = "google"
        logger.info("Starting Google Speech Recognition engine...")
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 2000
        self.recognizer.dynamic_energy_threshold = True

        def recognition_loop():
            with sr.Microphone(sample_rate=16000) as source:
                logger.info("Calibrating for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logger.info("✅ Google Recognition ready - Listening...")
                
                while self.is_running and self.current_engine == "google":
                    try:
                        audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=15)
                        def process_audio(audio_data):
                            try:
                                text = self.recognizer.recognize_google(audio_data).lower()
                                if text: 
                                    self.result_queue.put({
                                        'text': text,
                                        'engine': 'online',
                                        'timestamp': time.time()
                                    })
                            except (sr.UnknownValueError, sr.RequestError): pass
                        threading.Thread(target=process_audio, args=(audio,), daemon=True).start()
                    except sr.WaitTimeoutError: continue
        
        threading.Thread(target=recognition_loop, daemon=True).start()
    
    def run(self):
        """Main worker loop - runs in its own thread"""
        self.is_running = True
        logger.info("[ONLINE] Started")
        while self.is_running:
            time.sleep(0.1)
        logger.info("[ONLINE] Stopped")

    def stop(self):
        self.is_running = False
        if self.ws:
            self.ws.close()
        logger.info("PureVoiceSTT system stopped")

class CerberusSTTService:
    """Main STT Service with mode switching"""
    
    def __init__(self):
        self.config = STTConfig()
        self.parser = GBNFCommandParser()
        
        # Mode control
        self.mode = "auto"  # "offline", "online", or "auto"
        self.current_engine = None
        self.is_running = True
        self.loop = None  # Will store the event loop
        
        # Thread references
        self.current_worker_thread = None
        
        # Result queue for all engines
        self.result_queue = queue.Queue()
        
        # Engines
        self.offline_engine = OfflineSTTEngine(self.config, self.parser, self.result_queue)
        self.online_engine = OnlineSTTEngine(self.config, self.result_queue)
        
        # NATS
        self.nc = None
    
    async def connect_nats(self):
        """Connect to NATS server"""
        try:
            self.nc = await nats.connect("nats://localhost:4222")
            logger.info("[STT] Connected to NATS")
            return True
        except Exception as e:
            logger.error(f"[STT] Failed to connect to NATS: {e}")
            return False
    
    def check_internet(self) -> bool:
        """Check internet connectivity"""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return True
        except:
            return False
    
    async def check_internet_async(self) -> bool:
        """Check internet connectivity WITHOUT blocking the async loop"""
        # Run the blocking socket check in an executor thread pool
        return await self.loop.run_in_executor(
            None,  # Use default executor
            self.check_internet
        )

    async def determine_mode(self) -> str:
        """Determine which mode to use (async-safe)"""
        if self.mode == "auto":
            has_internet = await self.check_internet_async()
            logger.info(f"[STT] Internet check: {has_internet}")
            return "online" if has_internet else "offline"
        return self.mode
    
    def start_engine_thread(self, engine_type: str):
        """Start the specified engine in a new thread"""
        # Stop any existing engine first
        self.stop_engine_thread()
        
        if engine_type == "online":
            self.current_worker_thread = threading.Thread(
                target=self.online_engine.run,
                daemon=True,
                name="OnlineSTT"
            )
            self.current_engine = "online"
        else:
            self.current_worker_thread = threading.Thread(
                target=self.offline_engine.run,
                daemon=True,
                name="OfflineSTT"
            )
            self.current_engine = "offline"
        
        self.current_worker_thread.start()
        logger.info(f"[STT] Started {engine_type} engine thread")

    def stop_engine_thread(self):
        """Stop current engine thread"""
        if self.current_engine == "online":
            self.online_engine.stop()
        elif self.current_engine == "offline":
            self.offline_engine.stop()
        
        # Wait for thread to finish (with timeout)
        if self.current_worker_thread and self.current_worker_thread.is_alive():
            self.current_worker_thread.join(timeout=2.0)
        
        self.current_worker_thread = None
        self.current_engine = None

    async def set_mode(self, new_mode: str):
        if new_mode not in ["offline", "online", "auto"]:
            logger.warning(f"Invalid mode: {new_mode}")
            return
        
        # Avoid restart if the requested mode is already active
        if self.mode == new_mode and self.current_engine is not None:
            return
        
        # Stop any currently running engine thread
        self.stop_engine_thread()
        self.mode = new_mode
        logger.info(f"[STT] Setting mode to: {self.mode}")
        
        # Determine engine type asynchronously and start it
        engine_type = await self.determine_mode()
        self.start_engine_thread(engine_type)

    async def handle_control(self, msg):
        """Handle control messages from NATS"""
        try:
            data = json.loads(msg.data.decode())
            new_mode = data.get("mode", "auto")
            if new_mode in ["offline", "online", "auto"]:
                await self.set_mode(new_mode)
        except Exception as e:
            logger.error(f"Control error: {e}")
    
    async def run(self):
        """Main service loop - purely async"""
        self.loop = asyncio.get_event_loop()
        
        if not await self.connect_nats():
            return

        await self.nc.subscribe("stt.control", cb=self.handle_control)
        logger.info("[STT] Service ready")
        
        # Start in the default auto mode
        await self.set_mode(self.mode)
        
        # This is the main non-blocking loop
        while self.is_running:
            try:
                # Safely get a result from the worker thread's queue without blocking
                result = await self.loop.run_in_executor(
                    None, lambda: self.result_queue.get(timeout=1.0)
                )
                
                # A result was found, publish it to the correct NATS subject
                if result.get("engine") == "offline":
                    # Offline engine provides already-parsed commands
                    await self.nc.publish("stt.command.parsed", json.dumps(result["data"]).encode())
                else:
                    # Online engine provides raw text. Try to parse to a command first.
                    text = result.get('text', '')
                    command = self.parser.parse_command(text)
                    if command:
                        await self.nc.publish("stt.command.parsed", json.dumps(command).encode())
                    else:
                        await self.nc.publish("stt.transcription.online", json.dumps(result).encode())

            except queue.Empty:
                # This is normal, means no speech was detected in the last second
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Main loop error: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        self.is_running = False
        self.stop_engine_thread()

if __name__ == "__main__":
    service = CerberusSTTService()
    
    # Register cleanup
    atexit.register(service.cleanup)
    
    try:
        # Run the async service
        asyncio.run(service.run())
    except KeyboardInterrupt:
        logger.info("\n[STT] Shutting down...")
    finally:
        service.cleanup()