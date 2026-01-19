"""Documentation generation module.

Provides assembly instruction generation and post-processing guides.
"""

from src.docs.assembly_generator import (
    AssemblyGenerator,
    AssemblyConfig,
    AssemblyPart,
    AssemblyStep,
    AssemblyInstructions,
    ConnectionType,
    create_generator,
    generate_instructions,
)

from src.docs.post_processing import (
    PostProcessingGuide,
    ProcessingGuide,
    ProcessStep,
    ProcessType,
    FinishLevel,
    create_guide,
    get_finish_steps,
)

__all__ = [
    # Assembly generator
    "AssemblyGenerator",
    "AssemblyConfig",
    "AssemblyPart",
    "AssemblyStep",
    "AssemblyInstructions",
    "ConnectionType",
    "create_generator",
    "generate_instructions",
    # Post-processing
    "PostProcessingGuide",
    "ProcessingGuide",
    "ProcessStep",
    "ProcessType",
    "FinishLevel",
    "create_guide",
    "get_finish_steps",
]
