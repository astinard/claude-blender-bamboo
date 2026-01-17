"""
JARVIS Voice System

Text-to-speech and speech recognition for sci-fi voice interaction.
Uses macOS 'say' command for TTS (no dependencies required).
"""

import subprocess
import threading
import queue
import time
import sys
import os
from typing import Optional, Callable, List
from dataclasses import dataclass


@dataclass
class VoiceConfig:
    """Voice configuration."""
    voice: str = "Samantha"  # macOS voice (try: Daniel, Samantha, Alex, Tessa)
    rate: int = 200  # Words per minute (default ~175-200)
    volume: float = 1.0  # 0.0 to 1.0
    enabled: bool = True


# Jarvis personality phrases
JARVIS_GREETINGS = [
    "Good {time_of_day}. Fabrication systems are online.",
    "Welcome back. All systems operational.",
    "Fab Lab initialized. Ready for your command.",
    "Systems check complete. How may I assist you?",
]

JARVIS_CONFIRMATIONS = [
    "Right away.",
    "Understood.",
    "Processing your request.",
    "Initiating sequence.",
    "As you wish.",
    "Consider it done.",
]

JARVIS_COMPLETIONS = [
    "Task complete.",
    "Operation successful.",
    "Done.",
    "Fabrication sequence complete.",
    "Ready for next command.",
]

JARVIS_ERRORS = [
    "I've encountered a problem.",
    "There seems to be an issue.",
    "I'm afraid I can't do that.",
    "An error has occurred.",
]

JARVIS_THINKING = [
    "Analyzing...",
    "Processing...",
    "Computing optimal solution...",
    "Running diagnostics...",
    "Calculating parameters...",
]


class JarvisVoice:
    """
    Jarvis voice interface with text-to-speech.

    Uses macOS 'say' command for zero-dependency TTS.
    """

    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self._speech_queue = queue.Queue()
        self._speaking = False
        self._speech_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Start speech worker thread
        self._start_worker()

    def _start_worker(self):
        """Start the speech worker thread."""
        self._stop_event.clear()
        self._speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self._speech_thread.start()

    def _speech_worker(self):
        """Background worker that processes speech queue."""
        while not self._stop_event.is_set():
            try:
                text = self._speech_queue.get(timeout=0.1)
                self._speaking = True
                self._speak_sync(text)
                self._speaking = False
                self._speech_queue.task_done()
            except queue.Empty:
                continue

    def _speak_sync(self, text: str):
        """Synchronously speak text using macOS say command."""
        if not self.config.enabled:
            return

        try:
            # Build say command
            cmd = ["say"]

            # Add voice
            if self.config.voice:
                cmd.extend(["-v", self.config.voice])

            # Add rate
            if self.config.rate:
                cmd.extend(["-r", str(self.config.rate)])

            # Add text
            cmd.append(text)

            # Execute
            subprocess.run(cmd, capture_output=True, check=True)

        except FileNotFoundError:
            # 'say' not available (not macOS)
            pass
        except subprocess.CalledProcessError:
            pass

    def speak(self, text: str, block: bool = False):
        """
        Speak text.

        Args:
            text: Text to speak
            block: If True, wait for speech to complete
        """
        if block:
            self._speak_sync(text)
        else:
            self._speech_queue.put(text)

    def speak_greeting(self):
        """Speak a random greeting."""
        import random
        hour = time.localtime().tm_hour
        if hour < 12:
            time_of_day = "morning"
        elif hour < 17:
            time_of_day = "afternoon"
        else:
            time_of_day = "evening"

        greeting = random.choice(JARVIS_GREETINGS)
        self.speak(greeting.format(time_of_day=time_of_day))

    def speak_confirmation(self):
        """Speak a random confirmation."""
        import random
        self.speak(random.choice(JARVIS_CONFIRMATIONS))

    def speak_completion(self):
        """Speak a random completion message."""
        import random
        self.speak(random.choice(JARVIS_COMPLETIONS))

    def speak_error(self, details: str = ""):
        """Speak an error message."""
        import random
        error = random.choice(JARVIS_ERRORS)
        if details:
            self.speak(f"{error} {details}")
        else:
            self.speak(error)

    def speak_thinking(self):
        """Speak a thinking message."""
        import random
        self.speak(random.choice(JARVIS_THINKING))

    def wait(self):
        """Wait for all speech to complete."""
        self._speech_queue.join()

    def stop(self):
        """Stop the voice system."""
        self._stop_event.set()
        # Kill any running say process
        subprocess.run(["killall", "say"], capture_output=True)

    def set_voice(self, voice: str):
        """Change the voice."""
        self.config.voice = voice

    def set_rate(self, rate: int):
        """Change speech rate."""
        self.config.rate = rate

    def enable(self):
        """Enable voice."""
        self.config.enabled = True

    def disable(self):
        """Disable voice."""
        self.config.enabled = False

    @staticmethod
    def list_voices() -> List[str]:
        """List available macOS voices."""
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True,
                check=True
            )
            voices = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    # Format: "Voice Name    language   # comment"
                    voice = line.split()[0]
                    voices.append(voice)
            return voices
        except:
            return ["Samantha", "Daniel", "Alex", "Tessa", "Karen"]


class SpeechRecognizer:
    """
    Speech recognition for voice commands.

    Requires: pip install SpeechRecognition pyaudio
    """

    def __init__(self, wake_word: str = "jarvis"):
        self.wake_word = wake_word.lower()
        self._recognizer = None
        self._microphone = None
        self._listening = False
        self._callbacks: List[Callable[[str], None]] = []

        # Try to import speech_recognition
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone()
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        """Check if speech recognition is available."""
        return self._available

    def on_command(self, callback: Callable[[str], None]):
        """Register a callback for voice commands."""
        self._callbacks.append(callback)

    def listen_once(self, timeout: float = 5.0) -> Optional[str]:
        """
        Listen for a single voice command.

        Args:
            timeout: Maximum time to listen

        Returns:
            Recognized text or None
        """
        if not self._available:
            return None

        import speech_recognition as sr

        try:
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._recognizer.listen(source, timeout=timeout)

            # Use Google's free speech recognition
            text = self._recognizer.recognize_google(audio)
            return text.lower()

        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            return None

    def listen_for_wake_word(self, timeout: float = None) -> bool:
        """
        Listen for the wake word.

        Args:
            timeout: Maximum time to listen (None = forever)

        Returns:
            True if wake word detected
        """
        text = self.listen_once(timeout or 10.0)
        if text and self.wake_word in text:
            return True
        return False

    def start_continuous(self):
        """Start continuous listening in background."""
        if not self._available:
            return

        self._listening = True
        thread = threading.Thread(target=self._continuous_listen, daemon=True)
        thread.start()

    def stop_continuous(self):
        """Stop continuous listening."""
        self._listening = False

    def _continuous_listen(self):
        """Continuous listening loop."""
        while self._listening:
            text = self.listen_once(timeout=3.0)
            if text:
                # Check for wake word
                if self.wake_word in text:
                    # Extract command after wake word
                    parts = text.split(self.wake_word, 1)
                    if len(parts) > 1:
                        command = parts[1].strip()
                        for callback in self._callbacks:
                            callback(command)


# Convenience functions

_default_voice: Optional[JarvisVoice] = None

def get_voice() -> JarvisVoice:
    """Get the default voice instance."""
    global _default_voice
    if _default_voice is None:
        _default_voice = JarvisVoice()
    return _default_voice

def speak(text: str, block: bool = False):
    """Speak text using the default voice."""
    get_voice().speak(text, block=block)

def listen(timeout: float = 5.0) -> Optional[str]:
    """Listen for a voice command."""
    recognizer = SpeechRecognizer()
    if recognizer.available:
        return recognizer.listen_once(timeout)
    return None


# Demo
if __name__ == "__main__":
    print("JARVIS Voice System Demo")
    print("=" * 50)

    voice = JarvisVoice()

    print("\nAvailable voices:", voice.list_voices()[:10])

    print("\nSpeaking greeting...")
    voice.speak_greeting()
    voice.wait()

    print("Speaking confirmation...")
    voice.speak("Scanning object. Please hold steady.")
    voice.wait()

    print("Speaking status...")
    voice.speak("Scan complete. 847,000 polygons captured. Mesh is watertight.")
    voice.wait()

    print("Speaking completion...")
    voice.speak_completion()
    voice.wait()

    print("\nDemo complete!")
