import sys
import json
import requests
import base64
import io
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QScrollArea, QFileDialog, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QImage
from PIL import Image


class WorkflowRunner(QThread):
    """Thread to run ComfyUI workflow without blocking UI"""
    finished = pyqtSignal(object)  # Emits image data or None
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, prompt_text, server_address="127.0.0.1:8188"):
        super().__init__()
        self.prompt_text = prompt_text
        self.server_address = server_address
        self.workflow = None
        
    def load_workflow(self):
        """Load and modify the workflow with the new prompt"""
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
                    "width": 512,
                    "height": 512,
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
                    "seed": 898303157960251,
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
            workflow = self.load_workflow()
            
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
        
        # Disable generate button during generation
        self.generate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        
        self.log_status("Starting image generation...")
        
        # Create and start worker thread
        self.worker = WorkflowRunner(prompt)
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
