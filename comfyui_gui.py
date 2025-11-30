import sys
import json
import requests
import base64
import io
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QScrollArea, QFileDialog, QMessageBox, QComboBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QImage
from PIL import Image


class WorkflowRunner(QThread):
    """Thread to run ComfyUI workflow without blocking UI"""
    finished = pyqtSignal(object)  # Emits image data or None
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, prompt_text, server_address="127.0.0.1:8188", seed=None, width=512, height=512):
        super().__init__()
        self.prompt_text = prompt_text
        self.server_address = server_address
        self.workflow = None
        self.seed = seed
        self.width = width
        self.height = height
        
    def load_workflow(self, width=512, height=512):
        """Load and modify the workflow with the new prompt"""
        import random
        
        # Generate random seed if not provided
        if self.seed is None:
            self.seed = random.randint(0, 2**32 - 1)
        
        # Base workflow structure from the JSON
        workflow = {
            "27": {
                "inputs": {
                    "text": self.prompt_text,
                    "clip": ["30", 0]
                },
                "class_type": "CLIPTextEncode"
            },
            "30": {
                "inputs": {
                    "clip_name": "qwen_3_4b.safetensors",
                    "type": "lumina2"
                },
                "class_type": "CLIPLoader"
            },
            "29": {
                "inputs": {
                    "vae_name": "ae.safetensors"
                },
                "class_type": "VAELoader"
            },
            "28": {
                "inputs": {
                    "unet_name": "z_image_turbo_bf16.safetensors",
                    "weight_dtype": "default"
                },
                "class_type": "UNETLoader"
            },
            "13": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                },
                "class_type": "EmptySD3LatentImage"
            },
            "11": {
                "inputs": {
                    "shift": 3.0,
                    "model": ["28", 0]
                },
                "class_type": "ModelSamplingAuraFlow"
            },
            "33": {
                "inputs": {
                    "conditioning": ["27", 0]
                },
                "class_type": "ConditioningZeroOut"
            },
            "3": {
                "inputs": {
                    "seed": self.seed,
                    "steps": 4,
                    "cfg": 1.0,
                    "sampler_name": "res_multistep",
                    "scheduler": "simple",
                    "denoise": 1.0,
                    "model": ["11", 0],
                    "positive": ["27", 0],
                    "negative": ["33", 0],
                    "latent_image": ["13", 0]
                },
                "class_type": "KSampler"
            },
            "8": {
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["29", 0]
                },
                "class_type": "VAEDecode"
            },
            "9": {
                "inputs": {
                    "filename_prefix": "z-image",
                    "images": ["8", 0]
                },
                "class_type": "SaveImage"
            }
        }
        return workflow
    
    def run(self):
        """Execute the workflow"""
        try:
            self.status.emit("Loading workflow...")
            workflow = self.load_workflow(self.width, self.height)
            
            self.status.emit("Queuing prompt to ComfyUI...")
            prompt_data = {"prompt": workflow}
            
            response = requests.post(
                f"http://{self.server_address}/prompt",
                json=prompt_data,
                timeout=300
            )
            
            if response.status_code != 200:
                self.error.emit(f"Failed to queue prompt: {response.text}")
                self.finished.emit(None)
                return
            
            result = response.json()
            prompt_id = result.get('prompt_id')
            
            if not prompt_id:
                self.error.emit("No prompt_id received from server")
                self.finished.emit(None)
                return
            
            self.status.emit(f"Prompt queued (ID: {prompt_id}). Generating image...")
            
            # Poll for completion
            image_data = self.wait_for_completion(prompt_id)
            
            if image_data:
                self.status.emit("Image generated successfully!")
                self.finished.emit(image_data)
            else:
                self.error.emit("Failed to retrieve generated image")
                self.finished.emit(None)
                
        except requests.exceptions.ConnectionError:
            self.error.emit(f"Cannot connect to ComfyUI at {self.server_address}. Is it running?")
            self.finished.emit(None)
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")
            self.finished.emit(None)
    
    def wait_for_completion(self, prompt_id, max_attempts=120):
        """Wait for the workflow to complete and return image data"""
        import time
        
        for attempt in range(max_attempts):
            try:
                # Check history for this prompt
                history_response = requests.get(
                    f"http://{self.server_address}/history/{prompt_id}",
                    timeout=10
                )
                
                if history_response.status_code == 200:
                    history = history_response.json()
                    
                    if prompt_id in history:
                        outputs = history[prompt_id].get('outputs', {})
                        
                        # Look for SaveImage node output (node 9)
                        if '9' in outputs:
                            images = outputs['9'].get('images', [])
                            if images:
                                image_info = images[0]
                                filename = image_info['filename']
                                subfolder = image_info.get('subfolder', '')
                                
                                # Download the image
                                return self.download_image(filename, subfolder)
                
                time.sleep(2)  # Wait 2 seconds before checking again
                
            except Exception as e:
                self.status.emit(f"Polling error: {str(e)}")
                time.sleep(2)
        
        return None
    
    def download_image(self, filename, subfolder=''):
        """Download the generated image from ComfyUI"""
        try:
            params = {'filename': filename}
            if subfolder:
                params['subfolder'] = subfolder
            params['type'] = 'output'
            
            response = requests.get(
                f"http://{self.server_address}/view",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.content
            
        except Exception as e:
            self.error.emit(f"Failed to download image: {str(e)}")
        
        return None


class ComfyUIGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_image_data = None
        self.current_pixmap = None
        self.current_prompt = ""
        self.current_seed = None
        
        # Image size presets
        self.size_presets = {
            "512x512 (Square)": (512, 512),
            "768x768 (Square)": (768, 768),
            "1024x1024 (Square)": (1024, 1024),
            "512x768 (Portrait)": (512, 768),
            "768x1024 (Portrait)": (768, 1024),
            "768x512 (Landscape)": (768, 512),
            "1024x768 (Landscape)": (1024, 768),
            "1024x576 (16:9)": (1024, 576),
            "576x1024 (9:16)": (576, 1024),
        }
        
        # Aspect ratio presets
        self.aspect_ratios = {
            "1:1 (Square)": (1, 1),
            "4:3": (4, 3),
            "3:4": (3, 4),
            "16:9 (Widescreen)": (16, 9),
            "9:16 (Portrait)": (9, 16),
            "3:2": (3, 2),
            "2:3": (2, 3),
        }
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("ComfyUI Z-Image Turbo Generator")
        self.setGeometry(100, 100, 900, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Prompt text box
        prompt_label = QLabel("Prompt:")
        layout.addWidget(prompt_label)
        
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Enter your image generation prompt here...")
        self.prompt_text.setMaximumHeight(150)
        default_prompt = """A magazine cover photography of a smiling energetic 16-year-old Japanese girl with layered short hair, pushing a vintage bicycle in front of a retro mint green vending machine. Cheerful expression, lively posture, summer vibe. She wears a white T-shirt and denim overalls. Green grapes and a water cup in the bike basket. Background of messy telephone poles and nostalgic Japanese shop signs. Side sunlight creating a golden halo on her hair. Fujifilm Pro 400H style, grainy film texture, low saturation, slightly overexposed, cinematic composition, unique camera angle. Fashion editorial style, 8K resolution.

Magazine cover layout with visible text:
Large title "SUMMER" at the top.
Small cover text: "Youth & Freedom", "Tokyo Street Issue", "Vol. 24 | August 2025".
Barcode at the bottom corner."""
        self.prompt_text.setText(default_prompt)
        layout.addWidget(self.prompt_text)
        
        # Image size and aspect ratio controls
        size_controls_layout = QHBoxLayout()
        
        # Size preset dropdown
        size_label = QLabel("Image Size:")
        size_controls_layout.addWidget(size_label)
        
        self.size_combo = QComboBox()
        self.size_combo.addItems(self.size_presets.keys())
        self.size_combo.setCurrentText("512x512 (Square)")
        self.size_combo.currentTextChanged.connect(self.on_size_changed)
        size_controls_layout.addWidget(self.size_combo)
        
        size_controls_layout.addSpacing(20)
        
        # Aspect ratio dropdown
        aspect_label = QLabel("Aspect Ratio:")
        size_controls_layout.addWidget(aspect_label)
        
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(self.aspect_ratios.keys())
        self.aspect_combo.setCurrentText("1:1 (Square)")
        self.aspect_combo.currentTextChanged.connect(self.on_aspect_changed)
        size_controls_layout.addWidget(self.aspect_combo)
        
        size_controls_layout.addSpacing(20)
        
        # Base size input for aspect ratio calculation
        base_size_label = QLabel("Base Size:")
        size_controls_layout.addWidget(base_size_label)
        
        self.base_size_combo = QComboBox()
        self.base_size_combo.addItems(["512", "768", "1024"])
        self.base_size_combo.setCurrentText("512")
        self.base_size_combo.currentTextChanged.connect(self.on_aspect_changed)
        size_controls_layout.addWidget(self.base_size_combo)
        
        size_controls_layout.addStretch()
        
        layout.addLayout(size_controls_layout)
        
        # Current dimensions display
        self.dimensions_label = QLabel("Current: 512 x 512")
        self.dimensions_label.setStyleSheet("QLabel { color: #0066cc; font-weight: bold; }")
        layout.addWidget(self.dimensions_label)
        
        # Image preview area
        preview_label = QLabel("Generated Image:")
        layout.addWidget(preview_label)
        
        # Scrollable image area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(400)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText("No image generated yet")
        self.image_label.setStyleSheet("QLabel { background-color: #f0f0f0; border: 1px solid #ccc; }")
        
        scroll_area.setWidget(self.image_label)
        layout.addWidget(scroll_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("Generate Image")
        self.generate_btn.clicked.connect(self.generate_image)
        button_layout.addWidget(self.generate_btn)
        
        self.regenerate_btn = QPushButton("Re-Generate (New Seed)")
        self.regenerate_btn.clicked.connect(self.regenerate_image)
        self.regenerate_btn.setEnabled(False)
        button_layout.addWidget(self.regenerate_btn)
        
        self.save_btn = QPushButton("Save Image (JPG)")
        self.save_btn.clicked.connect(self.save_image)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)
        
        self.exit_btn = QPushButton("Exit")
        self.exit_btn.clicked.connect(self.close)
        button_layout.addWidget(self.exit_btn)
        
        layout.addLayout(button_layout)
        
        # Status box
        status_label = QLabel("Status and Messages:")
        layout.addWidget(status_label)
        
        self.status_box = QTextEdit()
        self.status_box.setReadOnly(True)
        self.status_box.setMaximumHeight(100)
        self.status_box.setPlaceholderText("Status messages will appear here...")
        layout.addWidget(self.status_box)
        
        # Initial status
        self.log_status("Ready. Enter a prompt and click 'Generate Image'.")
    
    def on_size_changed(self, size_text):
        """Handle size preset selection"""
        if size_text in self.size_presets:
            width, height = self.size_presets[size_text]
            self.dimensions_label.setText(f"Current: {width} x {height}")
            
            # Disable aspect ratio controls when using presets
            self.aspect_combo.setEnabled(False)
            self.base_size_combo.setEnabled(False)
    
    def on_aspect_changed(self):
        """Handle aspect ratio selection"""
        aspect_text = self.aspect_combo.currentText()
        base_size = int(self.base_size_combo.currentText())
        
        if aspect_text in self.aspect_ratios:
            ratio_w, ratio_h = self.aspect_ratios[aspect_text]
            
            # Calculate dimensions based on aspect ratio
            if ratio_w >= ratio_h:
                width = base_size
                height = int(base_size * ratio_h / ratio_w)
            else:
                height = base_size
                width = int(base_size * ratio_w / ratio_h)
            
            # Round to nearest multiple of 8 (common requirement for diffusion models)
            width = (width // 8) * 8
            height = (height // 8) * 8
            
            self.dimensions_label.setText(f"Current: {width} x {height}")
            
            # Enable aspect ratio controls
            self.aspect_combo.setEnabled(True)
            self.base_size_combo.setEnabled(True)
            
            # Update size combo to show it's custom
            self.size_combo.blockSignals(True)
            self.size_combo.setCurrentIndex(-1)
            self.size_combo.blockSignals(False)
    
    def get_current_dimensions(self):
        """Get the currently selected image dimensions"""
        size_text = self.size_combo.currentText()
        
        if size_text in self.size_presets:
            return self.size_presets[size_text]
        else:
            # Parse from dimensions label
            dims_text = self.dimensions_label.text()
            parts = dims_text.replace("Current:", "").strip().split("x")
            if len(parts) == 2:
                try:
                    width = int(parts[0].strip())
                    height = int(parts[1].strip())
                    return (width, height)
                except ValueError:
                    pass
            
            # Default fallback
            return (512, 512)
    
    def log_status(self, message):
        """Add a status message to the status box"""
        self.status_box.append(f"[{self.get_timestamp()}] {message}")
        # Auto-scroll to bottom
        cursor = self.status_box.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.status_box.setTextCursor(cursor)
    
    def get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def generate_image(self):
        """Start image generation"""
        prompt = self.prompt_text.toPlainText().strip()
        
        if not prompt:
            QMessageBox.warning(self, "No Prompt", "Please enter a prompt first!")
            return
        
        # Store current prompt and generate new seed
        self.current_prompt = prompt
        self.current_seed = None  # Will generate random seed
        
        # Get current dimensions
        width, height = self.get_current_dimensions()
        
        self._start_generation(prompt, None, width, height)
    
    def regenerate_image(self):
        """Regenerate image with same prompt but new seed"""
        if not self.current_prompt:
            QMessageBox.warning(self, "No Prompt", "Generate an image first!")
            return
        
        # Get current dimensions
        width, height = self.get_current_dimensions()
        
        # Use stored prompt with new random seed
        self._start_generation(self.current_prompt, None, width, height)
    
    def _start_generation(self, prompt, seed=None, width=512, height=512):
        """Internal method to start image generation"""
        # Disable buttons during generation
        self.generate_btn.setEnabled(False)
        self.regenerate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        
        self.log_status(f"Starting image generation ({width}x{height})...")
        
        # Create and start worker thread
        self.worker = WorkflowRunner(prompt, seed=seed, width=width, height=height)
        self.worker.status.connect(self.log_status)
        self.worker.error.connect(self.log_error)
        self.worker.finished.connect(self.on_generation_complete)
        self.worker.start()
    
    def log_error(self, message):
        """Log error message in red"""
        self.status_box.append(f'<span style="color: red;">[{self.get_timestamp()}] ERROR: {message}</span>')
        cursor = self.status_box.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.status_box.setTextCursor(cursor)
    
    def on_generation_complete(self, image_data):
        """Handle completion of image generation"""
        self.generate_btn.setEnabled(True)
        self.regenerate_btn.setEnabled(True)
        
        if image_data:
            try:
                # Convert image data to QPixmap
                image = Image.open(io.BytesIO(image_data))
                
                # Convert PIL Image to QPixmap
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                qimage = QImage.fromData(img_byte_arr.read())
                self.current_pixmap = QPixmap.fromImage(qimage)
                
                # Scale image to fit display
                scaled_pixmap = self.current_pixmap.scaled(
                    800, 600,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                self.image_label.setPixmap(scaled_pixmap)
                self.current_image_data = image_data
                self.save_btn.setEnabled(True)
                
                # Store the seed used for this generation
                if hasattr(self.worker, 'seed'):
                    self.current_seed = self.worker.seed
                    self.log_status(f"✓ Image generation completed successfully! (Seed: {self.current_seed})")
                else:
                    self.log_status("✓ Image generation completed successfully!")
                
            except Exception as e:
                self.log_error(f"Failed to display image: {str(e)}")
        else:
            self.log_error("Image generation failed. Check error messages above.")
    
    def save_image(self):
        """Save the generated image as JPG"""
        if not self.current_image_data:
            QMessageBox.warning(self, "No Image", "No image to save!")
            return
        
        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            "generated_image.jpg",
            "JPEG Images (*.jpg *.jpeg)"
        )
        
        if file_path:
            try:
                # Load image and convert to RGB (in case it has alpha channel)
                image = Image.open(io.BytesIO(self.current_image_data))
                
                if image.mode in ('RGBA', 'LA', 'P'):
                    # Convert to RGB
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    rgb_image.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                    image = rgb_image
                
                # Save as JPEG
                image.save(file_path, 'JPEG', quality=95)
                self.log_status(f"✓ Image saved successfully to: {file_path}")
                
                QMessageBox.information(self, "Success", f"Image saved to:\n{file_path}")
                
            except Exception as e:
                self.log_error(f"Failed to save image: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to save image:\n{str(e)}")


def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = ComfyUIGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
