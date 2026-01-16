# Ralph Loop Prompt: Blender + Bamboo Labs Integration

## Project Goal
Build an automated pipeline connecting Claude Code to Blender for 3D modeling and Bamboo Labs 3D printers for fabrication. Users should be able to describe objects in natural language, have them modeled in Blender, and sent to a Bamboo Labs printer.

## Success Criteria (Output this when ALL are met)
When the following are complete, output: `<promise>PROJECT COMPLETE</promise>`

1. **Environment Setup** - Python venv with all dependencies installed
2. **Blender Integration** - Scripts that can create/export 3D models headlessly
3. **Printer Communication** - Working MQTT connection to Bamboo Labs printers
4. **End-to-End Pipeline** - Complete workflow from prompt → model → export → print
5. **Tests Passing** - Basic tests for each component
6. **Documentation** - README with setup instructions

## Architecture

```
Claude Code → Blender (headless) → STL/3MF → Slicer → Bamboo MQTT → Print
```

## Phase Checklist

### Phase 1: Environment (Iterations 1-10)
- [ ] Create Python virtual environment
- [ ] Create requirements.txt with: bambulabs-api, paho-mqtt, pytest
- [ ] Create project structure:
  ```
  src/
    blender/        # Blender scripts
    printer/        # Bamboo Labs communication
    pipeline/       # Orchestration
  tests/
  config/
  ```
- [ ] Create config.py for settings (printer IP, access code placeholders)

### Phase 2: Blender Scripts (Iterations 11-25)
- [ ] Create `src/blender/primitives.py` - Generate basic shapes (cube, cylinder, sphere)
- [ ] Create `src/blender/exporter.py` - Export to STL/3MF
- [ ] Create `src/blender/mesh_utils.py` - Mesh validation (watertight check)
- [ ] Create wrapper script for headless execution
- [ ] Test: `blender --background --python test_script.py`

### Phase 3: Printer Communication (Iterations 26-35)
- [ ] Create `src/printer/connection.py` - MQTT client wrapper
- [ ] Create `src/printer/commands.py` - Print commands (start, pause, status)
- [ ] Create `src/printer/file_transfer.py` - FTP upload functionality
- [ ] Add mock printer for testing without hardware

### Phase 4: Pipeline Integration (Iterations 36-45)
- [ ] Create `src/pipeline/workflow.py` - Orchestrate full pipeline
- [ ] Create `src/pipeline/cli.py` - Command-line interface
- [ ] Add example prompts and templates
- [ ] Integration tests

### Phase 5: Polish (Iterations 46-50)
- [ ] Create comprehensive README.md
- [ ] Add error handling and logging
- [ ] Create example usage scripts
- [ ] Final testing and cleanup

## Key Technical Details

### Blender Headless
```bash
blender --background --python script.py -- --arg1 value1
```

### Bamboo MQTT
```python
from bambulabs_api import Printer
printer = Printer(ip="IP", access_code="CODE", serial="SERIAL")
printer.connect()
```

### File Formats
- Export: STL (universal) or 3MF (preferred for Bamboo)
- Slicing: Use Bambu Studio CLI or OrcaSlicer

## Current Status
Check git status and existing files to see what's been completed.

## Next Action
1. Read existing files to understand current state
2. Check off completed items in the checklist above
3. Work on the next uncompleted item
4. Run tests if applicable
5. Commit progress with descriptive message

## Important Notes
- Use placeholder values for printer credentials (user will configure)
- Blender may not be installed - create scripts that will work when it is
- Focus on modular, testable code
- Each iteration should make measurable progress
