# ComfyUI Z-Image Turbo GUI

A powerful PyQt6-based graphical interface for ComfyUI's Z-Image Turbo workflow, featuring AI-powered prompt generation via Ollama and batch processing capabilities.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)

## Features

- 🎨 **Simple Image Generation**: Generate images from text prompts with customizable sizes and aspect ratios
- 🤖 **AI Prompt Generation**: Use Ollama LLMs to expand simple phrases into detailed image prompts
- 🔄 **Re-generation**: Generate variations with different seeds while keeping the same prompt
- 📊 **Batch Mode**: Process multiple images from CSV files with automated prompt generation
- 💾 **Smart Auto-naming**: Automatically name saved images based on your concept phrases
- 🖼️ **Image Preview**: View generated images before saving
- 📏 **Flexible Sizing**: Choose from presets or use aspect ratio calculator

## Prerequisites

### Required Software

1. **Python 3.8 or higher**
   - Download from [python.org](https://www.python.org/downloads/)

2. **ComfyUI**
   - Install ComfyUI following the [official guide](https://github.com/comfyanonymous/ComfyUI)
   - Ensure ComfyUI is running on `http://127.0.0.1:8188`

3. **Ollama** (Optional, for AI prompt generation)
   - Download from [ollama.ai](https://ollama.ai/)
   - Pull at least one model: `ollama pull llama3.2`

## Installation

### Step 1: Clone or Download This Repository

```bash
git clone <repository-url>
cd comfyui-z-image-turbo-gui
```

Or download and extract the ZIP file.

### Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

The `requirements.txt` includes:
- PyQt6
- requests
- Pillow

### Step 3: Setup ComfyUI and Models

#### Install ComfyUI

Follow the [ComfyUI installation guide](https://github.com/comfyanonymous/ComfyUI#installing):

**Windows:**
```bash
# Using portable installation
# Download and extract ComfyUI portable version
# Run ComfyUI\run_nvidia_gpu.bat (or AMD/CPU variant)
```

**Linux/Mac:**
```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt
python main.py
```

#### Download Required Models

The Z-Image Turbo workflow requires these models:

1. **Text Encoder** (qwen_3_4b.safetensors)
   ```bash
   # Navigate to ComfyUI/models/text_encoders/
   # Download from:
   https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors
   ```

2. **Diffusion Model** (z_image_turbo_bf16.safetensors)
   ```bash
   # Navigate to ComfyUI/models/diffusion_models/
   # Download from:
   https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors
   ```

3. **VAE** (ae.safetensors)
   ```bash
   # Navigate to ComfyUI/models/vae/
   # Download from:
   https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors
   ```

#### Directory Structure

After downloading, your ComfyUI directory should look like:

```
ComfyUI/
├── models/
│   ├── text_encoders/
│   │   └── qwen_3_4b.safetensors
│   ├── diffusion_models/
│   │   └── z_image_turbo_bf16.safetensors
│   └── vae/
│       └── ae.safetensors
```

### Step 4: Setup Ollama (Optional)

If you want to use AI prompt generation:

1. **Install Ollama**
   - Download from [ollama.ai](https://ollama.ai/)
   - Follow installation instructions for your OS

2. **Pull a model**
   ```bash
   ollama pull llama3.2
   # or
   ollama pull mistral
   # or any other model
   ```

3. **Verify Ollama is running**
   - Check that Ollama is accessible at `http://127.0.0.1:11434`
   - The GUI will automatically detect available models

## Usage

### Starting the Application

1. **Start ComfyUI**
   ```bash
   cd ComfyUI
   python main.py
   # Or on Windows: run_nvidia_gpu.bat
   ```
   
   Verify ComfyUI is running at `http://127.0.0.1:8188`

2. **Start Ollama** (if using AI prompt generation)
   ```bash
   # Ollama should auto-start on most systems
   # Or manually: ollama serve
   ```

3. **Run the GUI**
   ```bash
   python comfyui_gui.py
   ```

### Basic Workflow

#### Single Image Generation

1. **Option A: Write your own prompt**
   - Enter a detailed prompt in the "Image Prompt" text box
   - Click "Generate Image"

2. **Option B: Use AI prompt generation**
   - Enter a simple concept in "Concept/Phrase" (e.g., "sunset over mountains")
   - Select an Ollama model
   - Click "✨ Generate Prompt"
   - Review the generated prompt
   - Click "Generate Image"

3. **Customize image size**
   - Select from preset sizes (512x512, 1024x1024, etc.)
   - Or choose aspect ratio + base size

4. **Save the image**
   - Click "Save Image (JPG)"
   - Auto-generated filename: `phrase_0001.jpg`

5. **Generate variations**
   - Click "Re-Generate (New Seed)" for different versions

### Batch Mode

Process multiple images from a CSV file:

1. **Click "📊 Batch Mode"**

2. **Prepare your CSV file**
   ```csv
   phrase,description
   sunset mountains,warm golden hour colors
   cyberpunk city,neon lights and rain
   forest path,misty morning atmosphere
   ```

3. **Load the CSV**
   - Click "📁 Load File"
   - Select CSV delimiter
   - Review/edit the spreadsheet

4. **Generate prompts**
   - Click "✨ Generate All Prompts"
   - Wait for AI to expand all phrases into detailed prompts

5. **Process batch**
   - Click "🎨 Process Batch (Generate Images)"
   - Monitor progress indicator

6. **Save results**
   - Click "💾 Save CSV" to save updated CSV with prompts
   - Click "💾 Save All Images" to export all JPGs to Output folder

### CSV Format

Your CSV file should have these columns:

| Column 1 | Column 2 | Column 3 | Column 4 |
|----------|----------|----------|----------|
| Phrase/Word | Description (optional) | Image Prompt (auto-filled) | Filename (auto-filled) |

Example:
```csv
sunset,warm colors,,
ocean waves,dramatic,,
mountain peak,snow covered,,
```

The app will automatically:
- Generate detailed prompts (column 3)
- Create filenames like `sunset_0001`, `ocean_waves_0002` (column 4)

## Configuration

### ComfyUI Connection

By default, the app connects to `http://127.0.0.1:8188`

To change this, modify in the code:
```python
server_address="127.0.0.1:8188"
```

### Ollama Connection

By default, connects to `http://127.0.0.1:11434`

To change this, modify in the code:
```python
ollama_url="http://127.0.0.1:11434"
```

### Image Generation Settings

Default workflow settings:
- **Steps**: 4 (Z-Image Turbo is optimized for few steps)
- **CFG Scale**: 1.0
- **Sampler**: res_multistep
- **Scheduler**: simple

These are optimized for Z-Image Turbo and shouldn't need changes.

## Troubleshooting

### "Cannot connect to ComfyUI"
- Ensure ComfyUI is running on port 8188
- Check `http://127.0.0.1:8188` in your browser
- Restart ComfyUI if needed

### "Cannot connect to Ollama"
- Check if Ollama is running: `ollama list`
- Start Ollama service: `ollama serve`
- Verify at `http://127.0.0.1:11434`

### "No models available"
- Pull an Ollama model: `ollama pull llama3.2`
- Click "🔄 Update Models" in the GUI

### "Failed to queue prompt"
- Verify all models are downloaded to correct folders
- Check ComfyUI console for error messages
- Ensure model files are not corrupted

### Images not generating
- Check ComfyUI is not frozen/crashed
- Monitor ComfyUI console for errors
- Verify GPU/CPU has enough memory
- Try smaller image sizes (512x512)

### Slow generation
- Z-Image Turbo is fast (4 steps), but first generation loads models
- Subsequent generations should be much faster
- Batch mode processes sequentially, so larger batches take time
- Consider GPU upgrade for faster processing

## Tips and Best Practices

### Prompt Engineering
- Use Ollama to expand simple concepts into detailed prompts
- Include style keywords: "photorealistic", "anime", "oil painting"
- Specify lighting: "golden hour", "studio lighting", "dramatic shadows"
- Add technical details: "8K resolution", "cinematic composition"

### Batch Processing
- Start with small batches (10-20 items) to test
- Keep prompts under 300 words for best results
- Use descriptive phrases in column 1 for better auto-naming
- Monitor the status box for errors during batch processing

### Image Sizes
- 512x512: Fastest, good for testing
- 768x768: Balanced quality/speed
- 1024x1024: Highest quality, slower
- Use aspect ratios for specific compositions (16:9 for landscapes, 9:16 for portraits)

### Performance
- Close other GPU-intensive applications
- First generation is slower (model loading)
- Batch mode: generates images sequentially
- Use Re-Generate for quick variations

## File Outputs

### Single Mode
- Images saved as: `phrase_0001.jpg`, `phrase_0002.jpg`, etc.
- Location: User-selected directory

### Batch Mode
- CSV saved with prompts and filenames
- All images saved to: `selected_directory/Output/`
- Filenames from column 4 of spreadsheet

## License

MIT License - Feel free to modify and distribute

## Credits

- ComfyUI: [comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- Z-Image Turbo Model: [Comfy-Org](https://huggingface.co/Comfy-Org/z_image_turbo)
- Ollama: [ollama.ai](https://ollama.ai/)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify all prerequisites are installed correctly
3. Check ComfyUI and Ollama logs for errors
4. Open an issue on GitHub with error details

## Changelog

### Version 1.0.0
- Initial release
- Single image generation
- AI prompt generation with Ollama
- Batch mode processing
- Auto-naming and CSV export
- Image size presets and aspect ratios
