"""
JARVIS - Just A Rather Very Intelligent System

Sci-fi voice and visual interface for the Fab Lab.
"Good evening. Fabrication systems are online."
"""

from .voice import JarvisVoice, speak, listen
from .display import JarvisDisplay, show_banner, show_status
from .sounds import JarvisSounds, SoundType, play, click, confirm, error, success
from .core import Jarvis

__all__ = [
    "Jarvis",
    "JarvisVoice",
    "JarvisDisplay",
    "JarvisSounds",
    "SoundType",
    "speak",
    "listen",
    "play",
    "click",
    "confirm",
    "error",
    "success",
    "show_banner",
    "show_status",
]
