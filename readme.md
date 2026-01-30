
A powerful PyQt6-based graphical interface for ComfyUI's Z-Image Turbo workflow, featuring AI-powered prompt generation via Ollama and batch processing capabilities.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-green.svg)

## Features

- 🎨 **Simple Image Generation**: Generate images from text prompts with customizable sizes and aspect ratios
- 🤖 **AI Prompt Generation**: Use Ollama LLMs to expand simple phrases into detailed image prompts
- 🎭 **Style Selection**: Choose from 44+ preset styles or define custom styles for consistent aesthetics
- 🔄 **Re-generation**: Generate variations with different seeds while keeping the same prompt
- 📊 **Batch Mode**: Process multiple images from CSV files with automated prompt generation
- 💾 **Smart Auto-naming**: Automatically name saved images based on your concept phrases
- 🖼️ **Image Preview**: View generated images before saving
- 📏 **Flexible Sizing**: Choose from presets or use aspect ratio calculator
- 🔀 **Multi-Workflow Support**: Load and use any ComfyUI workflow JSON file
- 📡 **Server Status**: Real-time ComfyUI server connection monitoring

## Tested Workflows

The GUI has been tested and verified to work with the following workflows:

### ✅ Default: Z-Image Turbo (Built-in)
- **Model**: z_image_turbo_bf16.safetensors
- **Steps**: 4 (optimized for speed)
- **Sampler**: res_multistep
- **Features**: Ultra-fast generation, built-in workflow
- **Best for**: Quick iterations, testing prompts
- **File**: `image_z_image_turbo_t1.json`

### ✅ FLUX Schnell
- **Model**: flux1-schnell-fp8.safetensors
- **Steps**: 4 (distilled model)
- **Sampler**: euler
- **CFG**: 1.0 (no negative prompt support)
- **Features**: High-quality fast generation, modern architecture
- **Best for**: High-quality results with minimal steps
- **File**: `flux_quick.json`
- **Note**: Negative prompts are ignored (CFG=1.0)

### ✅ Flux2 Klein Distilled

This workflow uses the Flux2 Klein distilled model, a compact yet powerful variant optimized for efficient image generation.

* **File:** `flux2_klein_distilled.json`
* **UNET Model:** `flux-2-klein-4b.safetensors`
* **CLIP Model:** `qwen_3_4b.safetensors`
* **VAE Model:** `flux2-vae.safetensors`
* **Sampler:** `euler`
* **Scheduler:** `simple`
* **Steps:** 4
* **CFG:** 1
* **Guidance:** 3.5

- **Features**: Compact yet powerful Flux2 Klein distilled model
- **Best for**: Efficient image generation with balanced quality and speed
- **Note**: Negative prompts are ignored (CFG=1.0)

### ✅ SDXL Turbo
- **Model**: sd_xl_turbo_1.0_fp16.safetensors
- **Steps**: 4
- **Sampler**: euler_ancestral
- **CFG**: 1.1
- **Features**: SDXL quality with turbo speed
- **Best for**: Balanced quality and speed with SDXL architecture
- **File**: `SDXLturbo_Quick2.json`

### ✅ Juggernaut XL
- **Model**: juggernautXL_ragnarokBy.safetensors
- **Steps**: 28 (high quality)
- **Sampler**: dpmpp_2m
- **Scheduler**: karras
- **CFG**: 4.0
- **Features**: High-quality photorealistic results
- **Best for**: Detailed, photorealistic images (slower generation)
- **File**: `JuggernautXL.json`

### ✅ Qwen Image Rapid
- **Model**: Qwen-Rapid-AIO-SFW-v8.safetensors
- **Steps**: 4
- **Sampler**: sa_solver
- **Scheduler**: beta
- **Features**: Custom text encoding with TextEncodeQwenImageEditPlus
- **Best for**: Fast generation with Qwen architecture
- **File**: `Qwen Image Rapid.json`
- **Note**: Uses custom `prompt` field instead of `text`

### ✅ NetaYume Lumina (Modified)
- **Model**: NetaYumev35_pretrained_all_in_one.safetensors
- **Steps**: 30
- **Sampler**: res_multistep
- **CFG**: 4.0
- **Features**: High-quality anime-style generation, ModelSamplingAuraFlow
- **Best for**: Anime and artistic illustrations
- **File**: `image_netayume_lumina_t2i_mod.json`
- **Note**: Requires simplified workflow without subgraphs
- **Model Link**: [Download from HuggingFace](https://huggingface.co/duongve/NetaYume-Lumina-Image-2.0/resolve/main/NetaYumev35_pretrained_all_in_one.safetensors)

## Workflow Compatibility

The GUI intelligently handles different workflow formats:
- ✅ Standard ComfyUI workflows (CheckpointLoaderSimple)
- ✅ Custom node types (TextEncodeQwenImageEditPlus, etc.)
- ✅ Different text input fields (`text`, `prompt`, `string`)
- ✅ Various latent image nodes (EmptyLatentImage, EmptySD3LatentImage)
- ✅ Model sampling nodes (ModelSamplingAuraFlow, ModelSamplingFlux)
- ✅ Automatic filtering of UI-only nodes (Notes, MarkdownNote)
- ✅ Smart detection of positive vs negative prompts
- ⚠️ **Limited support for subgraphs** - workflows with nested subgraphs should be simplified

### Unsupported Workflow Features
- ❌ Complex subgraphs with UUID node types
- ❌ Deeply nested custom node structures
- ❌ Workflows requiring custom prompt formatters
- ⚠️ Some advanced ControlNet configurations

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

The GUI includes a built-in Z-Image Turbo workflow. For other workflows, download the appropriate models:

**For Z-Image Turbo (Built-in):**

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

**For FLUX Schnell:**
- Model: [flux1-schnell-fp8.safetensors](https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors)
- Location: `ComfyUI/models/checkpoints/`

**For SDXL Turbo:**
- Model: [sd_xl_turbo_1.0_fp16.safetensors](https://huggingface.co/stabilityai/sdxl-turbo)
- Location: `ComfyUI/models/checkpoints/`

**For Juggernaut XL:**
- Model: [juggernautXL_ragnarokBy.safetensors](https://civitai.com/models/133005/juggernaut-xl)
- Location: `ComfyUI/models/checkpoints/`

**For NetaYume Lumina:**
- Model: [NetaYumev35_pretrained_all_in_one.safetensors](https://huggingface.co/duongve/NetaYume-Lumina-Image-2.0/resolve/main/NetaYumev35_pretrained_all_in_one.safetensors)
- Location: `ComfyUI/models/checkpoints/`
- **Note**: Use the modified workflow (`image_netayume_lumina_t2i_mod.json`) without subgraphs

#### Directory Structure

After downloading, your ComfyUI directory should look like:

```
ComfyUI/
├── models/
│   ├── checkpoints/
│   │   ├── flux1-schnell-fp8.safetensors
│   │   ├── flux-2-klein-4b.safetensors
│   │   ├── sd_xl_turbo_1.0_fp16.safetensors
│   │   ├── juggernautXL_ragnarokBy.safetensors
│   │   ├── Qwen-Rapid-AIO-SFW-v8.safetensors
│   │   └── NetaYumev35_pretrained_all_in_one.safetensors
│   ├── text_encoders/
│   │   └── qwen_3_4b.safetensors
│   ├── diffusion_models/
│   │   └── z_image_turbo_bf16.safetensors
│   └── vae/
│       ├── ae.safetensors
│       └── flux2-vae.safetensors
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
   - **Select a style** (Photorealistic, Oil Painting, Anime, etc.) or use Custom
   - Click "✨ Generate Prompt"
   - Review the generated prompt
   - Click "Generate Image"

3. **Option C: Load a custom workflow**
   - Click "📂 Load Workflow"
   - Select a ComfyUI workflow JSON file
   - Verify "✓ Custom Loaded" appears in green
   - Enter your prompt and generate

4. **Customize image size**
   - Select from preset sizes (512x512, 1024x1024, etc.)
   - Or choose aspect ratio + base size

5. **Save the image**
   - Click "Save Image (JPG)"
   - Auto-generated filename: `phrase_0001.jpg`

6. **Generate variations**
   - Click "Re-Generate (New Seed)" for different versions

### Using Custom Workflows

The GUI supports loading any ComfyUI workflow:

1. **Export workflow from ComfyUI**
   - In ComfyUI, click "Save (API Format)" or export as JSON
   - Save the workflow file

2. **Load in GUI**
   - Click "📂 Load Workflow"
   - Select your workflow JSON file
   - Check the status indicators:
     - **🟢 Online** = ComfyUI server is running
     - **✓ Custom Loaded** = Workflow loaded successfully
     - **✗ Load Failed** = Check error messages

3. **Generate with custom workflow**
   - Your prompt will replace the positive prompt in the workflow
   - Negative prompts are preserved
   - Image dimensions are updated
   - Seeds are randomized (or regenerated)

4. **Reset to default**
   - Click "🔄 Reset to Default" to return to Z-Image Turbo

### Workflow Tips

- **FLUX models**: Set CFG to 1.0, negative prompts are ignored
- **Turbo models**: Use 4 steps for optimal speed/quality balance
- **High-quality models** (Juggernaut): Use 20-30 steps, higher CFG
- **Custom nodes**: The GUI automatically adapts to different text field names

### Batch Mode

Process multiple images from a CSV file:

1. **Click "📊 Batch Mode"**

2. **Prepare your CSV file**
   
   Default delimiter is **Pipe (|)**:
   ```
   phrase|description
   sunset mountains|warm golden hour colors
   cyberpunk city|neon lights and rain
   forest path|misty morning atmosphere
   ```
   
   Or use other delimiters (Comma, Tab, Semicolon):
   ```csv
   phrase,description
   sunset mountains,warm golden hour colors
   cyberpunk city,neon lights and rain
   ```

3. **Load and configure**
   - Click "📁 Load File" and select your CSV
   - Select CSV delimiter (default: Pipe |)
   - Choose Ollama model for prompt generation
   - **Select style** (applies to all prompts in batch)
   - Review/edit the spreadsheet data

4. **Generate content**
   - **✨ Generate All**: Creates full prompts, pronunciations, and IPA for all rows
   - **🔤 Gen Pronunciation**: Creates only pronunciations and IPA transcriptions
   - **📝 Gen Image Prompt**: Creates only image prompts (no pronunciation)
   - **⏹ Cancel Generation**: Stops any ongoing generation process
   - Wait for AI to process your content
   - Results appear in respective columns

5. **Process batch**
   - Click "🎨 Process Batch (Generate Images)"
   - Monitor progress indicator (current/total)
   - Watch status messages for any errors

6. **Save results**
   - **💾 Save CSV**: Saves to `Output/` folder with original filename
   - **💾 Save All Images**: Exports all JPGs to `Output/Output/` folder
   - **📦 Save All as Zip**: Creates zip with CSV + all images in `Output/` folder
   - **❌ Exit**: Close batch mode dialog

### CSV Format

Your CSV file should have these columns:

**Note**: Column 2 was renamed from "Description" to "Translation" for better semantic clarity.

| Column 1 | Column 2 | Column 3 | Column 4 | Column 5 | Column 6 |
|----------|----------|----------|----------|----------|----------|
| Phrase/Word | Translation (optional) | Pronunciation (auto-generated) | IPA (auto-generated) | Image Prompt (auto-filled) | Filename (auto-filled) |

**Example with Pipe delimiter (|):**
```
sunset|warm colors|||photorealistic image of sunset with warm golden and orange colors|
mountain peak|snow covered|||majestic snow-covered mountain peak under blue sky|
ancient temple|mysterious|||mysterious ancient temple hidden in misty jungle|
```

**Example with Comma delimiter (,):**
```csv
sunset,warm colors,,,photorealistic image of sunset with warm golden and orange colors,
ocean waves,dramatic,,,dramatic ocean waves crashing against rocky shore,
mountain peak,snow covered,,,majestic snow-covered mountain peak under blue sky,
```

The app will automatically:
- Generate detailed prompts (column 5)
- Create filenames like `sunset_0001`, `ocean_waves_0002` (column 6)
- Generate pronunciations in English phonetic spelling (column 3)
- Generate IPA (International Phonetic Alphabet) symbols (column 4)

### Batch Mode Features

- **Individual Controls**: Each row has buttons to regenerate prompt or image
- **Image Preview**: Click any row to see its generated image
- **Flexible Delimiters**: Pipe (default), Comma, Tab, or Semicolon
- **Model Selection**: Choose Ollama model per batch
- **Style Consistency**: Apply one style to all images in batch
- **Selective Generation**: Generate full content, pronunciation only, or descriptions only
- **Cancellation Support**: Stop generation processes mid-way
- **Smart Saving**: 
  - CSV saves to `Output/` with original filename
  - Images save to `Output/Output/` folder
  - Zip creates single file with everything
- **Progress Tracking**: Real-time status and error reporting

## Style Selection

The GUI includes 42+ preset styles organized into categories for consistent image generation:

### Available Style Categories

**Photographic & Realistic:**
- Photorealistic, Cinematic Film Still, Analog Film, Film Noir
- Portrait Photography, Food Photography, Macro Photography
- Street Photography, Old Photograph (BW/Colorized)

**Artistic & Painting:**
- Oil Painting, Watercolor, Acrylic, Pencil Sketch (BW/Color)
- Charcoal Drawing (BW/Color), Pen and Ink, Digital Painting
- Surrealism, Impressionism

**Graphic & Stylized:**
- Illustration, Anime, Comic Book, Graphic Novel
- Pixel Art, Vector Graphics, Flat Design

**3D & Rendering:**
- 3D Rendering, Octane Render/Unreal Engine
- Lowpoly, Isometric, Blender Render

**Genre & Aesthetic:**
- Cyberpunk, Neonpunk, Steampunk, Fantasy, Sci-Fi
- Art Deco, Art Nouveau, Minimalist, Vintage/Retro
- Concept Art

### Using Styles

**In Main Window:**
1. Select style from dropdown (default: Photorealistic)
2. Or choose "Custom" and enter your own style description
3. Style guides AI prompt generation for consistent results

**In Batch Mode:**
1. Select style before generating prompts
2. One style applies to entire batch
3. Creates consistent visual aesthetic across all images

**Custom Styles:**
- Select "Custom" from dropdown
- Enter any style description (e.g., "Ukiyo-e woodblock print", "Studio Ghibli animation")
- AI incorporates your custom style into prompts

## Configuration

### Default Settings

The application includes these default configurations:

- **Ollama Model**: `kimi-k2:1t-cloud` (auto-selected if available)
- **Style**: Photorealistic (for AI prompt generation)
- **CSV Delimiter**: Pipe (|) in batch mode
- **Output Directory**: `Output/` subdirectory in current working directory
- **Image Format**: JPEG with 95% quality
- **Batch Zip Naming**: Original filename + `_batch.zip`

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
- Click "🔍 Check" button to verify server status
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
- For custom workflows, verify the model name matches your file

### "Workflow loaded but image not generated"
- Check ComfyUI console for errors
- Verify SaveImage node is present in workflow
- Ensure all required models are installed
- Check if workflow uses custom nodes (may need installation)

### Images not generating
- Check ComfyUI is not frozen/crashed
- Monitor ComfyUI console for errors
- Verify GPU/CPU has enough memory
- Try smaller image sizes (512x512)
- Check if correct checkpoint/model is loaded

### Workflow loading errors
- **"Cannot execute because node X does not exist"**: Missing custom nodes
- **"Required input is missing"**: GUI couldn't parse workflow correctly
- **"Invalid workflow format"**: File may be corrupted or wrong format
- Try exporting workflow as "API Format" from ComfyUI

### Custom workflow issues
- Use "Save (API Format)" when exporting from ComfyUI
- Avoid workflows with UI-only nodes in critical paths
- Check that text encode nodes use standard field names
- Verify checkpoint names match your installed models

### Slow generation
- Z-Image Turbo / FLUX Schnell: Fast (4 steps)
- SDXL Turbo: Moderate (4 steps)
- Juggernaut XL: Slow (28 steps)
- First generation loads models (slower)
- Subsequent generations should be much faster
- Batch mode processes sequentially
- Consider GPU upgrade for faster processing

## Tips and Best Practices

### Prompt Engineering
- Use Ollama to expand simple concepts into detailed prompts
- **Select appropriate style** for your desired aesthetic
- Include style keywords: "photorealistic", "anime", "oil painting"
- Specify lighting: "golden hour", "studio lighting", "dramatic shadows"
- Add technical details: "8K resolution", "cinematic composition"
- **Style consistency**: Use same style across related images

### Ollama Model Selection
- **Default**: `kimi-k2:1t-cloud` (auto-selected if available)
- **Alternative models**: llama3.2, mistral, phi, etc.
- **Batch mode**: Can use different model than main window
- Install multiple models for flexibility: `ollama pull <model>`

### Style Selection Tips
- **Photography projects**: Use Photographic & Realistic styles
- **Artistic rendering**: Choose from Artistic & Painting styles
- **Comics/Animation**: Select Graphic & Stylized options
- **Game assets**: Use 3D & Rendering styles
- **Themed collections**: Genre & Aesthetic styles
- **Consistency**: Keep same style for series of images
- **Experimentation**: Try Custom styles for unique aesthetics
- **Batch uniformity**: One style per batch creates cohesive sets

### Workflow Selection
- **Quick testing**: Z-Image Turbo (4 steps, fastest)
- **High quality + speed**: FLUX Schnell (4 steps, best balance)
- **SDXL architecture**: SDXL Turbo (4 steps, SDXL quality)
- **Photorealistic**: Juggernaut XL (28 steps, highest quality)
- **Qwen architecture**: Qwen Rapid (4 steps, alternative fast option)
- **Anime style**: NetaYume Lumina (30 steps, anime/artistic)

### Batch Processing
- **CSV Format**: Use Pipe (|) delimiter by default for better compatibility
- **Test first**: Start with 5-10 items to verify workflow
- **Monitor progress**: Watch status box for errors during generation
- **Save incrementally**: Save CSV after prompt generation, before image processing
- **Zip for backup**: Use "Save All as Zip" for complete backup with images and data
- **Selective Generation**: Use specific buttons to generate only what you need
- **Cancellation**: Use "Cancel Generation" button to stop ongoing processes
- Keep prompts under 300 words for best results
- Use descriptive phrases in column 1 for better auto-naming

### Image Sizes
- **512x512**: Fastest, good for testing
- **768x768**: Balanced quality/speed
- **1024x1024**: Highest quality, slower
- Use aspect ratios for specific compositions (16:9 for landscapes, 9:16 for portraits)
- Note: Some models work better at specific resolutions (SDXL prefers 1024x1024)

### File Organization
- **Output folder**: All batch files auto-save to `Output/` directory
- **Naming**: CSV uses original filename, Zip adds `_batch` suffix
- **Cleanup**: Regularly backup and clear Output folder for large batches
- **Version control**: Zip files include both CSV and images for easy archiving

### Performance
- Close other GPU-intensive applications
- First generation is slower (model loading)
- Batch mode: generates images sequentially
- Use Re-Generate for quick variations
- Turbo models (4 steps) are 5-7x faster than standard models (28+ steps)

### Custom Workflows
- Export workflows as "API Format" from ComfyUI
- Test workflows in ComfyUI first before loading in GUI
- Keep workflows simple for better compatibility
- Avoid deeply nested or overly complex node structures
- The GUI preserves negative prompts automatically

## File Outputs

### Single Mode
- Images saved as: `phrase_0001.jpg`, `phrase_0002.jpg`, etc.
- Location: User-selected directory
- Format: JPEG, 95% quality

### Batch Mode

#### CSV Files
- **Location**: `Output/` subdirectory (auto-created)
- **Filename**: Same as input file (e.g., `mydata.csv` → `Output/mydata.csv`)
- **Format**: Same delimiter as input file (Pipe | by default)
- **Contents**: Phrase, Description, Pronunciation, IPA, Generated Prompt, Filename

#### Images
- **Location**: `Output/Output/` subdirectory
- **Filenames**: From column 6 of spreadsheet (e.g., `sunset_0001.jpg`)
- **Format**: JPEG, 95% quality

#### Zip Archives
- **Location**: `Output/` subdirectory
- **Filename**: Input name + `_batch.zip` (e.g., `mydata_batch.zip`)
- **Contents**:
  - `batch_data.csv` - Complete data table
  - `images/` folder - All generated images
- **Compression**: ZIP_DEFLATED

### Directory Structure After Batch Processing

```
YourProject/
├── Output/
│   ├── mydata.csv              # Saved CSV
│   ├── mydata_batch.zip        # Complete batch archive
│   └── Output/
│       ├── sunset_0001.jpg     # Individual images
│       ├── ocean_0002.jpg
│       └── mountain_0003.jpg
```

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
- Single image generation with Z-Image Turbo
- AI prompt generation with Ollama
- Batch mode processing with CSV export
- Auto-naming and image preview
- Image size presets and aspect ratios
- Multi-workflow support (load custom JSON workflows)
- Real-time server status monitoring
- Smart workflow parsing for different node types
- Support for custom text encoding nodes
- Automatic detection of positive/negative prompts
- Tested with 5 different workflow types:
  - Z-Image Turbo (default)
  - FLUX Schnell
  - SDXL Turbo
  - Juggernaut XL
  - Qwen Image Rapid

### Version 1.1.0
- **Default Ollama Model**: Auto-selects `kimi-k2:1t-cloud` if available
- **Batch Mode Enhancements**:
  - CSV delimiter default changed to Pipe (|)
  - Added Ollama model selection dropdown in batch mode
  - Moved "Generate All Prompts" button next to model selection
  - CSV auto-saves to Output folder with original filename
  - Added "Save All as Zip" button for complete batch archives
  - Added Exit button to batch mode dialog
  - Improved file organization with Output subdirectory
- **Better File Management**:
  - Smart default paths for all save operations
  - Automatic Output directory creation
  - Zip archives include CSV + all images
  - Filename preservation for batch workflows

### Version 1.2.0 (Latest)
- **Enhanced Workflow Display**:
  - Main window shows workflow filename next to Load Workflow button
  - Batch mode displays loaded CSV filename above spreadsheet
  - Batch mode has independent workflow loading
  - Workflow filename shown in batch mode controls
- **Batch Mode Image Controls**:
  - Added image size presets dropdown
  - Added aspect ratio calculator with base size
  - Real-time dimension display
  - Independent from main window settings
- **Expanded Workflow Support**:
  - Added support for ModelSamplingAuraFlow nodes
  - Added support for ModelSamplingFlux nodes
  - Better handling of model sampling parameters
  - NetaYume Lumina workflow support (modified version)
- **Workflow Compatibility**:
  - 6 tested and verified workflows
  - Subgraph detection and skipping
  - Improved node type detection
  - Better widget value mapping

### Version 1.3.0
- **Style Selection System**:
  - 44+ preset styles organized in 5 categories
  - Photographic & Realistic (10 styles)
  - Artistic & Painting (11 styles)
  - Graphic & Stylized (7 styles)
  - 3D & Rendering (5 styles)
  - Genre & Aesthetic (11 styles)
  - Custom style option for unlimited flexibility
  - Visual group separators in dropdown
  - Non-selectable category headers
- **AI Prompt Enhancement**:
  - Style-guided prompt generation
  - Main window style selection
  - Batch mode style consistency
  - Custom style text input
  - Context-aware AI instructions
- **User Interface**:
  - Organized style dropdown with categories
  - Bold, gray category headers
  - Clean visual hierarchy
  - Default: Photorealistic style

### Version 1.4.1
- **Additional Artistic Styles**:
  - Added "Acrylic" painting style to Artistic & Painting category
  - Added "Pen and Ink" drawing style to Artistic & Painting category
  - Updated style separator indices to maintain proper UI organization
  - Style count increased from 42 to 44 total preset styles

### Version 1.4.3 (Latest)
- **Batch Mode UI Refinements**:
  - Renamed column 2 from "Description" to "Translation" for better semantic clarity
  - Simplified button labels for conciseness:
    - "✨ Generate All Prompts" → "✨ Generate All"
    - "🔤 Gen Pronunciation" (formerly "Generate Pronunciation")
    - "📝 Gen Image Prompt" (formerly "Generate Description")
  - All functionality preserved with more intuitive naming
- **Enhanced Language Support**:
  - Added "Greek Polytonic" language option for better classical Greek text processing
  - Expanded multilingual capabilities for diverse linguistic needs
- **Improved Button State Management**:
  - Fixed "Cancel Generation" button activation issues
  - Ensured consistent button enable/disable behavior across all generation modes
  - Added centralized button state reset functionality
- **Pronunciation Generation Fixes**:
  - Resolved issues with "Generate Pronunciation" not updating word list
  - Improved data format handling for pronunciation-only generation
  - Enhanced fallback mechanisms for pronunciation generation
- **UI Consistency**:
  - Synchronized button states across all generation completion handlers
  - Improved error handling and user feedback
  - Better visual feedback during generation processes

### Version 1.4.0
- **Multilingual Support**:
  - Added language selection dropdown in batch mode (Greek default)
  - Language sent to AI for better prompt generation while keeping prompts in English
  - **Available languages**: Greek, Greek Polytonic, English, Spanish, French, German, Italian, Portuguese, Russian, Chinese, Japanese, Korean
- **Pronunciation Features**:
  - Added Pronunciation column (column 3) with English phonetic spelling
  - Added IPA column (column 4) with International Phonetic Alphabet symbols
  - AI generates both pronunciation and IPA for each phrase/word
  - Pronunciation data saved in CSV exports
  - Columns auto-populated during batch processing
- **Batch Mode Enhancements**:
  - Table now has 8 columns (was 6)
  - Improved column organization and labeling
  - Better data consistency in exports
  - Language dropdown added to main window as well

## Known Limitations

- Custom nodes must be installed in ComfyUI (not included in GUI)
- Batch mode processes images sequentially (no parallel processing)
- Maximum token size for Ollama prompts depends on model
- Image preview shows scaled version optimized for display (full resolution preserved for saving)
- Workflow parsing is best-effort for complex/unusual workflows
- Some workflow features (like ControlNet) may not be fully configurable via GUI
- **Subgraph workflows**: Complex nested subgraphs are not fully supported
  - Workflows using UUID-based subgraph nodes should be simplified
  - Use standard ComfyUI nodes (CLIPTextEncode, etc.) instead
  - Example: NetaYume Lumina requires modified workflow without subgraphs
- **Model sampling nodes**: Supported types include:
  - `ModelSamplingAuraFlow` (Z-Image Turbo, NetaYume Lumina)
  - `ModelSamplingFlux` (FLUX models)
  - Standard samplers (`KSampler`)
