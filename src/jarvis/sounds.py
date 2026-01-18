"""
JARVIS Sound System

Sci-fi sound effects and ambient audio for immersive experience.
Uses synthesized audio - no external files required.
"""

import subprocess
import threading
import queue
import time
import wave
import struct
import math
import os
import tempfile
from typing import Optional, Dict, Callable
from dataclasses import dataclass
from enum import Enum


class SoundType(Enum):
    """Types of sound effects."""
    # UI Sounds
    BOOT = "boot"
    READY = "ready"
    CLICK = "click"
    CONFIRM = "confirm"
    ERROR = "error"
    WARNING = "warning"

    # Action Sounds
    SCAN_START = "scan_start"
    SCAN_LOOP = "scan_loop"
    SCAN_COMPLETE = "scan_complete"
    PROCESSING = "processing"
    SUCCESS = "success"

    # Printer Sounds
    PRINT_START = "print_start"
    PRINT_LAYER = "print_layer"
    PRINT_COMPLETE = "print_complete"

    # Ambient
    AMBIENT_HUM = "ambient_hum"
    POWER_UP = "power_up"
    POWER_DOWN = "power_down"


@dataclass
class SoundConfig:
    """Sound system configuration."""
    enabled: bool = True
    volume: float = 0.7  # 0.0 to 1.0
    ambient_enabled: bool = True
    effects_enabled: bool = True


class SoundGenerator:
    """Generate synthesized sci-fi sounds."""

    SAMPLE_RATE = 44100

    @classmethod
    def generate_tone(
        cls,
        frequency: float,
        duration: float,
        volume: float = 0.5,
        fade_in: float = 0.01,
        fade_out: float = 0.01,
        wave_type: str = "sine"
    ) -> bytes:
        """Generate a tone with envelope."""
        num_samples = int(cls.SAMPLE_RATE * duration)
        samples = []

        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE

            # Generate wave
            if wave_type == "sine":
                value = math.sin(2 * math.pi * frequency * t)
            elif wave_type == "square":
                value = 1.0 if math.sin(2 * math.pi * frequency * t) > 0 else -1.0
            elif wave_type == "sawtooth":
                value = 2.0 * (t * frequency - math.floor(0.5 + t * frequency))
            elif wave_type == "triangle":
                value = 2.0 * abs(2.0 * (t * frequency - math.floor(0.5 + t * frequency))) - 1.0
            else:
                value = math.sin(2 * math.pi * frequency * t)

            # Apply envelope
            envelope = 1.0
            if t < fade_in:
                envelope = t / fade_in
            elif t > duration - fade_out:
                envelope = (duration - t) / fade_out

            value *= envelope * volume
            samples.append(value)

        return cls._samples_to_bytes(samples)

    @classmethod
    def generate_sweep(
        cls,
        start_freq: float,
        end_freq: float,
        duration: float,
        volume: float = 0.5,
        wave_type: str = "sine"
    ) -> bytes:
        """Generate a frequency sweep."""
        num_samples = int(cls.SAMPLE_RATE * duration)
        samples = []

        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE
            progress = t / duration

            # Logarithmic frequency sweep
            freq = start_freq * math.pow(end_freq / start_freq, progress)

            # Generate wave
            if wave_type == "sine":
                value = math.sin(2 * math.pi * freq * t)
            else:
                value = math.sin(2 * math.pi * freq * t)

            # Envelope
            envelope = 1.0
            if t < 0.01:
                envelope = t / 0.01
            elif t > duration - 0.01:
                envelope = (duration - t) / 0.01

            value *= envelope * volume
            samples.append(value)

        return cls._samples_to_bytes(samples)

    @classmethod
    def generate_noise(cls, duration: float, volume: float = 0.3) -> bytes:
        """Generate white noise."""
        import random
        num_samples = int(cls.SAMPLE_RATE * duration)
        samples = []

        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE
            value = random.uniform(-1, 1)

            # Envelope
            envelope = 1.0
            if t < 0.01:
                envelope = t / 0.01
            elif t > duration - 0.01:
                envelope = (duration - t) / 0.01

            value *= envelope * volume
            samples.append(value)

        return cls._samples_to_bytes(samples)

    @classmethod
    def generate_beep_sequence(
        cls,
        frequencies: list,
        durations: list,
        gap: float = 0.05,
        volume: float = 0.5
    ) -> bytes:
        """Generate a sequence of beeps."""
        all_samples = []

        for freq, dur in zip(frequencies, durations):
            # Tone
            tone_data = cls.generate_tone(freq, dur, volume)
            all_samples.extend(cls._bytes_to_samples(tone_data))

            # Gap
            gap_samples = int(cls.SAMPLE_RATE * gap)
            all_samples.extend([0.0] * gap_samples)

        return cls._samples_to_bytes(all_samples)

    @classmethod
    def generate_chord(
        cls,
        frequencies: list,
        duration: float,
        volume: float = 0.4
    ) -> bytes:
        """Generate a chord (multiple frequencies)."""
        num_samples = int(cls.SAMPLE_RATE * duration)
        samples = []

        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE
            value = 0.0

            for freq in frequencies:
                value += math.sin(2 * math.pi * freq * t)

            value /= len(frequencies)

            # Envelope
            envelope = 1.0
            if t < 0.02:
                envelope = t / 0.02
            elif t > duration - 0.05:
                envelope = (duration - t) / 0.05

            value *= envelope * volume
            samples.append(value)

        return cls._samples_to_bytes(samples)

    @classmethod
    def generate_pulse(cls, frequency: float, pulse_rate: float, duration: float, volume: float = 0.5) -> bytes:
        """Generate a pulsing tone."""
        num_samples = int(cls.SAMPLE_RATE * duration)
        samples = []

        for i in range(num_samples):
            t = i / cls.SAMPLE_RATE

            # Carrier wave
            carrier = math.sin(2 * math.pi * frequency * t)

            # Pulse modulation
            pulse = 0.5 + 0.5 * math.sin(2 * math.pi * pulse_rate * t)

            value = carrier * pulse * volume

            # Envelope
            if t < 0.01:
                value *= t / 0.01
            elif t > duration - 0.01:
                value *= (duration - t) / 0.01

            samples.append(value)

        return cls._samples_to_bytes(samples)

    @classmethod
    def _samples_to_bytes(cls, samples: list) -> bytes:
        """Convert float samples to bytes."""
        byte_data = b''
        for sample in samples:
            # Clamp to [-1, 1]
            sample = max(-1.0, min(1.0, sample))
            # Convert to 16-bit integer
            int_sample = int(sample * 32767)
            byte_data += struct.pack('<h', int_sample)
        return byte_data

    @classmethod
    def _bytes_to_samples(cls, byte_data: bytes) -> list:
        """Convert bytes to float samples."""
        samples = []
        for i in range(0, len(byte_data), 2):
            int_sample = struct.unpack('<h', byte_data[i:i+2])[0]
            samples.append(int_sample / 32767.0)
        return samples


class JarvisSounds:
    """
    JARVIS sound effects system.

    Generates and plays sci-fi sound effects for the interface.
    """

    def __init__(self, config: Optional[SoundConfig] = None):
        self.config = config or SoundConfig()
        self._sound_queue = queue.Queue()
        self._ambient_process: Optional[subprocess.Popen] = None
        self._stop_event = threading.Event()
        self._sound_cache: Dict[str, str] = {}  # Sound type -> temp file path
        self._temp_dir = tempfile.mkdtemp(prefix="jarvis_sounds_")

        # Pre-generate common sounds
        self._generate_sound_library()

        # Start sound worker
        self._start_worker()

    def _generate_sound_library(self):
        """Pre-generate all sound effects."""
        gen = SoundGenerator

        # Boot sequence - ascending tones
        self._cache_sound(
            SoundType.BOOT,
            gen.generate_beep_sequence(
                [200, 300, 400, 600, 800],
                [0.1, 0.1, 0.1, 0.1, 0.2],
                gap=0.02,
                volume=0.4
            )
        )

        # Ready chime - pleasant chord
        self._cache_sound(
            SoundType.READY,
            gen.generate_chord([523.25, 659.25, 783.99], 0.5, volume=0.4)  # C5, E5, G5
        )

        # Click - short high beep
        self._cache_sound(
            SoundType.CLICK,
            gen.generate_tone(1200, 0.05, volume=0.3, fade_in=0.005, fade_out=0.02)
        )

        # Confirm - two-tone up
        self._cache_sound(
            SoundType.CONFIRM,
            gen.generate_beep_sequence([600, 900], [0.1, 0.15], gap=0.02, volume=0.4)
        )

        # Error - descending harsh tones
        self._cache_sound(
            SoundType.ERROR,
            gen.generate_beep_sequence(
                [400, 300, 200],
                [0.15, 0.15, 0.2],
                gap=0.05,
                volume=0.5
            )
        )

        # Warning - pulsing tone
        self._cache_sound(
            SoundType.WARNING,
            gen.generate_pulse(440, 4, 0.8, volume=0.4)
        )

        # Scan start - sweep up
        self._cache_sound(
            SoundType.SCAN_START,
            gen.generate_sweep(200, 2000, 0.5, volume=0.4)
        )

        # Scan loop - pulsing radar sound
        self._cache_sound(
            SoundType.SCAN_LOOP,
            gen.generate_pulse(800, 2, 2.0, volume=0.25)
        )

        # Scan complete - satisfying confirmation
        self._cache_sound(
            SoundType.SCAN_COMPLETE,
            gen.generate_beep_sequence(
                [400, 600, 800, 1000],
                [0.08, 0.08, 0.08, 0.2],
                gap=0.02,
                volume=0.4
            )
        )

        # Processing - subtle working sound
        self._cache_sound(
            SoundType.PROCESSING,
            gen.generate_pulse(600, 3, 1.5, volume=0.2)
        )

        # Success - triumphant chord
        self._cache_sound(
            SoundType.SUCCESS,
            gen.generate_chord([523.25, 659.25, 783.99, 1046.5], 0.6, volume=0.45)
        )

        # Print start - mechanical startup
        self._cache_sound(
            SoundType.PRINT_START,
            gen.generate_sweep(100, 400, 0.8, volume=0.4)
        )

        # Print layer - subtle tick
        self._cache_sound(
            SoundType.PRINT_LAYER,
            gen.generate_tone(300, 0.03, volume=0.2, fade_in=0.005, fade_out=0.01)
        )

        # Print complete - achievement sound
        self._cache_sound(
            SoundType.PRINT_COMPLETE,
            gen.generate_beep_sequence(
                [523.25, 659.25, 783.99, 1046.5, 1318.5],
                [0.1, 0.1, 0.1, 0.1, 0.3],
                gap=0.03,
                volume=0.45
            )
        )

        # Power up - dramatic sweep with harmonics
        power_up = gen.generate_sweep(50, 800, 1.5, volume=0.5)
        self._cache_sound(SoundType.POWER_UP, power_up)

        # Power down - reverse
        self._cache_sound(
            SoundType.POWER_DOWN,
            gen.generate_sweep(800, 50, 1.2, volume=0.4)
        )

        # Ambient hum - low frequency drone
        self._cache_sound(
            SoundType.AMBIENT_HUM,
            gen.generate_chord([60, 120, 180], 5.0, volume=0.08)
        )

    def _cache_sound(self, sound_type: SoundType, audio_data: bytes):
        """Cache a sound to a temp file."""
        filepath = os.path.join(self._temp_dir, f"{sound_type.value}.wav")

        with wave.open(filepath, 'w') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SoundGenerator.SAMPLE_RATE)
            wav.writeframes(audio_data)

        self._sound_cache[sound_type.value] = filepath

    def _start_worker(self):
        """Start the sound worker thread."""
        self._stop_event.clear()
        thread = threading.Thread(target=self._sound_worker, daemon=True)
        thread.start()

    def _sound_worker(self):
        """Background worker that plays sounds."""
        while not self._stop_event.is_set():
            try:
                sound_type, block = self._sound_queue.get(timeout=0.1)
                if sound_type in self._sound_cache:
                    self._play_file(self._sound_cache[sound_type])
                self._sound_queue.task_done()
            except queue.Empty:
                continue

    def _play_file(self, filepath: str):
        """Play an audio file using afplay (macOS)."""
        if not self.config.enabled or not self.config.effects_enabled:
            return

        try:
            # Calculate volume (afplay uses 0-255 scale)
            vol = int(self.config.volume * 255)
            subprocess.run(
                ["afplay", "-v", str(self.config.volume), filepath],
                capture_output=True,
                check=False
            )
        except FileNotFoundError:
            # afplay not available (not macOS)
            pass

    def play(self, sound_type: SoundType, block: bool = False):
        """
        Play a sound effect.

        Args:
            sound_type: Type of sound to play
            block: If True, wait for sound to complete
        """
        if not self.config.enabled:
            return

        if block:
            if sound_type.value in self._sound_cache:
                self._play_file(self._sound_cache[sound_type.value])
        else:
            self._sound_queue.put((sound_type.value, block))

    def boot_sequence(self):
        """Play the full boot sequence."""
        self.play(SoundType.POWER_UP, block=True)
        time.sleep(0.3)
        self.play(SoundType.BOOT, block=True)
        time.sleep(0.2)
        self.play(SoundType.READY, block=True)

    def start_ambient(self):
        """Start ambient background sound."""
        if not self.config.enabled or not self.config.ambient_enabled:
            return

        # Loop ambient sound
        def ambient_loop():
            while not self._stop_event.is_set():
                if SoundType.AMBIENT_HUM.value in self._sound_cache:
                    self._play_file(self._sound_cache[SoundType.AMBIENT_HUM.value])
                time.sleep(4.8)  # Slight overlap for continuous sound

        thread = threading.Thread(target=ambient_loop, daemon=True)
        thread.start()

    def stop_ambient(self):
        """Stop ambient sound."""
        # Kill any running afplay processes
        subprocess.run(["pkill", "-f", "ambient_hum"], capture_output=True)

    def scan_sequence(self, duration: float = 3.0):
        """Play scanning sound sequence."""
        self.play(SoundType.SCAN_START, block=True)

        # Loop scan sound
        loops = int(duration / 2.0)
        for _ in range(loops):
            self.play(SoundType.SCAN_LOOP, block=True)

        self.play(SoundType.SCAN_COMPLETE)

    def print_sequence(self, layers: int = 10):
        """Play print sequence sounds."""
        self.play(SoundType.PRINT_START, block=True)

        for _ in range(layers):
            time.sleep(0.3)
            self.play(SoundType.PRINT_LAYER)

        time.sleep(0.5)
        self.play(SoundType.PRINT_COMPLETE)

    def click(self):
        """Play click sound."""
        self.play(SoundType.CLICK)

    def confirm(self):
        """Play confirmation sound."""
        self.play(SoundType.CONFIRM)

    def error(self):
        """Play error sound."""
        self.play(SoundType.ERROR)

    def warning(self):
        """Play warning sound."""
        self.play(SoundType.WARNING)

    def success(self):
        """Play success sound."""
        self.play(SoundType.SUCCESS)

    def processing(self):
        """Play processing sound."""
        self.play(SoundType.PROCESSING)

    def set_volume(self, volume: float):
        """Set master volume (0.0 to 1.0)."""
        self.config.volume = max(0.0, min(1.0, volume))

    def enable(self):
        """Enable all sounds."""
        self.config.enabled = True

    def disable(self):
        """Disable all sounds."""
        self.config.enabled = False

    def stop(self):
        """Stop the sound system and clean up."""
        self._stop_event.set()
        self.stop_ambient()

        # Clean up temp files
        for filepath in self._sound_cache.values():
            try:
                os.remove(filepath)
            except:
                pass
        try:
            os.rmdir(self._temp_dir)
        except:
            pass


# Convenience functions
_default_sounds: Optional[JarvisSounds] = None


def get_sounds() -> JarvisSounds:
    """Get the default sounds instance."""
    global _default_sounds
    if _default_sounds is None:
        _default_sounds = JarvisSounds()
    return _default_sounds


def play(sound_type: SoundType, block: bool = False):
    """Play a sound using the default instance."""
    get_sounds().play(sound_type, block=block)


def click():
    """Play click sound."""
    get_sounds().click()


def confirm():
    """Play confirm sound."""
    get_sounds().confirm()


def error():
    """Play error sound."""
    get_sounds().error()


def success():
    """Play success sound."""
    get_sounds().success()


# Demo
if __name__ == "__main__":
    print("JARVIS Sound System Demo")
    print("=" * 50)

    sounds = JarvisSounds()

    print("\n1. Boot sequence...")
    sounds.boot_sequence()
    time.sleep(0.5)

    print("\n2. UI sounds...")
    print("   Click")
    sounds.click()
    time.sleep(0.3)
    print("   Confirm")
    sounds.confirm()
    time.sleep(0.5)
    print("   Warning")
    sounds.warning()
    time.sleep(1.0)
    print("   Error")
    sounds.error()
    time.sleep(0.8)
    print("   Success")
    sounds.success()
    time.sleep(0.8)

    print("\n3. Scan sequence...")
    sounds.scan_sequence(duration=2.0)
    time.sleep(0.5)

    print("\n4. Processing...")
    sounds.processing()
    time.sleep(2.0)

    print("\n5. Print sequence (5 layers)...")
    sounds.print_sequence(layers=5)
    time.sleep(1.0)

    print("\n6. Power down...")
    sounds.play(SoundType.POWER_DOWN, block=True)

    print("\nDemo complete!")
    sounds.stop()
