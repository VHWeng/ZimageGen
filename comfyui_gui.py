import sys
import json
import requests
import base64
import io
import re
import csv
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QScrollArea, QFileDialog, QMessageBox, QComboBox, 
                             QLineEdit, QGroupBox, QTableWidget, QTableWidgetItem,
                             QDialog, QHeaderView, QAbstractItemView, QFrame)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QPixmap, QImage, QColor
from PIL import Image


class WorkflowLoader(QThread):
    """Thread to load and validate ComfyUI workflow"""
    finished = pyqtSignal(bool, str, dict)  # success, message, workflow_data
    error = pyqtSignal(str)
    
    def __init__(self, workflow_path, server_address="127.0.0.1:8188"):
        super().__init__()
        self.workflow_path = workflow_path
        self.server_address = server_address
    
    def run(self):
        """Load and validate workflow file"""
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                workflow_data = json.load(f)
            
            # Check if it's a valid ComfyUI workflow
            if 'nodes' in workflow_data or 'prompt' in workflow_data:
                # Try to extract the actual workflow structure
                if 'nodes' in workflow_data:
                    # This is a full workflow with UI data
                    self.finished.emit(True, "Workflow loaded successfully", workflow_data)
                else:
                    # This might be just the prompt data
                    self.finished.emit(True, "Workflow loaded successfully", workflow_data)
            else:
                self.error.emit("Invalid workflow format")
                self.finished.emit(False, "Invalid workflow format", {})
                
        except json.JSONDecodeError as e:
            self.error.emit(f"Invalid JSON: {str(e)}")
            self.finished.emit(False, f"Invalid JSON: {str(e)}", {})
        except Exception as e:
            self.error.emit(f"Failed to load workflow: {str(e)}")
            self.finished.emit(False, f"Failed to load workflow: {str(e)}", {})


class ServerStatusChecker(QThread):
    """Thread to check ComfyUI server status"""
    status_update = pyqtSignal(bool, str)  # is_online, message
    
    def __init__(self, server_address="127.0.0.1:8188"):
        super().__init__()
        self.server_address = server_address
        self.running = True
    
    def run(self):
        """Check server status"""
        try:
            response = requests.get(
                f"http://{self.server_address}/system_stats",
                timeout=2
            )
            
            if response.status_code == 200:
                self.status_update.emit(True, "Online")
            else:
                self.status_update.emit(False, f"Error {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            self.status_update.emit(False, "Offline")
        except Exception as e:
            self.status_update.emit(False, "Error")
    
    def stop(self):
        """Stop the checker"""
        self.running = False


class BatchPromptGenerator(QThread):
    """Thread to generate multiple prompts in batch using Ollama JSON mode"""
    finished = pyqtSignal(list)  # Emits list of generated prompts
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total
    
    def __init__(self, batch_data, model, ollama_url="http://127.0.0.1:11434"):
        super().__init__()
        self.batch_data = batch_data  # List of (phrase, description) tuples
        self.model = model
        self.ollama_url = ollama_url
    
    def run(self):
        """Generate prompts in batch using JSON mode"""
        try:
            results = []
            batch_size = 10  # Process in batches to stay under token limits
            total_items = len(self.batch_data)
            
            for i in range(0, total_items, batch_size):
                batch = self.batch_data[i:i+batch_size]
                self.status.emit(f"Processing batch {i//batch_size + 1}...")
                
                # Create batch prompt
                items_json = []
                for idx, (phrase, desc) in enumerate(batch):
                    item = {"id": i + idx, "phrase": phrase}
                    if desc:
                        item["description"] = desc
                    items_json.append(item)
                
                system_prompt = """You are an expert at creating detailed image generation prompts.
For each item in the JSON array, create a detailed, vivid prompt suitable for an AI image generator.
Include details about: style, composition, lighting, mood, colors, and technical aspects.
Keep each prompt under 200 words. Return ONLY a JSON array with the same structure, adding a "prompt" field to each item."""

                user_prompt = f"Create detailed image generation prompts for these items:\n{json.dumps(items_json, indent=2)}"
                
                try:
                    response = requests.post(
                        f"{self.ollama_url}/api/generate",
                        json={
                            "model": self.model,
                            "prompt": f"{system_prompt}\n\n{user_prompt}",
                            "stream": False,
                            "format": "json"
                        },
                        timeout=300
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        generated_text = result.get('response', '').strip()
                        
                        # Parse JSON response
                        try:
                            prompts_data = json.loads(generated_text)
                            
                            # Handle both array and object responses
                            if isinstance(prompts_data, dict) and 'prompts' in prompts_data:
                                prompts_data = prompts_data['prompts']
                            
                            for item in prompts_data:
                                results.append(item.get('prompt', ''))
                            
                            self.progress.emit(len(results), total_items)
                            
                        except json.JSONDecodeError:
                            # Fallback: treat as text and split
                            self.error.emit(f"JSON parse error in batch {i//batch_size + 1}, using fallback")
                            for _ in batch:
                                results.append(generated_text[:500] if generated_text else "")
                    else:
                        self.error.emit(f"Batch {i//batch_size + 1} failed: {response.status_code}")
                        for _ in batch:
                            results.append("")
                            
                except Exception as e:
                    self.error.emit(f"Error in batch {i//batch_size + 1}: {str(e)}")
                    for _ in batch:
                        results.append("")
            
            self.status.emit("✓ Batch prompt generation completed!")
            self.finished.emit(results)
            
        except Exception as e:
            self.error.emit(f"Batch generation error: {str(e)}")
            self.finished.emit([])


class BatchImageGenerator(QThread):
    """Thread to generate multiple images in batch"""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    progress = pyqtSignal(int, int)  # current, total
    image_generated = pyqtSignal(int, object)  # row_index, image_data
    
    def __init__(self, batch_items, width=512, height=512, custom_workflow=None):
        super().__init__()
        self.batch_items = batch_items  # List of (prompt, filename) tuples
        self.width = width
        self.height = height
        self.custom_workflow = custom_workflow
    
    def run(self):
        """Generate images in batch"""
        try:
            total = len(self.batch_items)
            
            for idx, (prompt, filename) in enumerate(self.batch_items):
                self.status.emit(f"Generating image {idx + 1}/{total}: {filename}")
                self.progress.emit(idx + 1, total)
                
                # Generate image using WorkflowRunner logic
                worker = WorkflowRunner(
                    prompt, 
                    width=self.width, 
                    height=self.height,
                    custom_workflow=self.custom_workflow
                )
                workflow = worker.load_workflow(self.width, self.height)
                
                prompt_data = {"prompt": workflow}
                response = requests.post(
                    "http://127.0.0.1:8188/prompt",
                    json=prompt_data,
                    timeout=300
                )
                
                if response.status_code == 200:
                    result = response.json()
                    prompt_id = result.get('prompt_id')
                    
                    if prompt_id:
                        image_data = worker.wait_for_completion(prompt_id)
                        if image_data:
                            self.image_generated.emit(idx, image_data)
                        else:
                            self.error.emit(f"Failed to generate: {filename}")
                            self.image_generated.emit(idx, None)
                    else:
                        self.error.emit(f"No prompt_id for: {filename}")
                        self.image_generated.emit(idx, None)
                else:
                    self.error.emit(f"Failed to queue: {filename}")
                    self.image_generated.emit(idx, None)
            
            self.status.emit("✓ Batch image generation completed!")
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(f"Batch generation error: {str(e)}")
            self.finished.emit()


class BatchModeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.batch_data = []
        self.image_data = {}  # Store generated images by row index
        self.current_selected_row = -1
        self.active_workers = []  # Track active worker threads
        self.loaded_file_path = None  # Store loaded file path for default save name
        self.batch_custom_workflow = None  # Store batch-specific workflow
        self.batch_workflow_path = None  # Store workflow file path
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Batch Mode - Multi-Image Generation")
        self.setGeometry(100, 100, 1400, 800)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # File loading section
        file_layout = QHBoxLayout()
        
        self.load_file_btn = QPushButton("📁 Load File")
        self.load_file_btn.clicked.connect(self.load_file)
        file_layout.addWidget(self.load_file_btn)
        
        delimiter_label = QLabel("CSV Delimiter:")
        file_layout.addWidget(delimiter_label)
        
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems(["Comma (,)", "Tab", "Semicolon (;)", "Pipe (|)"])
        self.delimiter_combo.setCurrentText("Pipe (|)")  # Set default to Pipe
        file_layout.addWidget(self.delimiter_combo)
        
        file_layout.addSpacing(20)
        
        # Ollama model selection for batch mode
        ollama_label = QLabel("Ollama Model:")
        file_layout.addWidget(ollama_label)
        
        self.batch_ollama_combo = QComboBox()
        self.batch_ollama_combo.setMinimumWidth(200)
        file_layout.addWidget(self.batch_ollama_combo)
        
        # Populate with parent's models
        if self.parent_window:
            for i in range(self.parent_window.ollama_model_combo.count()):
                model = self.parent_window.ollama_model_combo.itemText(i)
                self.batch_ollama_combo.addItem(model)
            # Set to same as parent's current selection
            current_model = self.parent_window.ollama_model_combo.currentText()
            self.batch_ollama_combo.setCurrentText(current_model)
        
        self.gen_prompts_btn = QPushButton("✨ Generate All Prompts")
        self.gen_prompts_btn.clicked.connect(self.generate_all_prompts)
        file_layout.addWidget(self.gen_prompts_btn)
        
        file_layout.addStretch()
        layout.addLayout(file_layout)
        
        # Display loaded filename above table
        self.loaded_file_label = QLabel("No file loaded")
        self.loaded_file_label.setStyleSheet("QLabel { color: #0066cc; font-weight: bold; margin: 5px 0; }")
        layout.addWidget(self.loaded_file_label)
        
        # Main content area with image preview and table
        content_layout = QHBoxLayout()
        
        # Left side: Image preview
        preview_layout = QVBoxLayout()
        preview_label = QLabel("Image Preview:")
        preview_layout.addWidget(preview_label)
        
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setMinimumWidth(400)
        
        self.preview_image_label = QLabel()
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setText("No image selected")
        self.preview_image_label.setStyleSheet("QLabel { background-color: #f0f0f0; border: 1px solid #ccc; }")
        
        self.preview_scroll.setWidget(self.preview_image_label)
        preview_layout.addWidget(self.preview_scroll)
        
        content_layout.addLayout(preview_layout, 1)
        
        # Right side: Spreadsheet table
        table_layout = QVBoxLayout()
        table_label = QLabel("Batch Data (Editable):")
        table_layout.addWidget(table_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Phrase/Word", "Description", "Image Prompt", "Filename", "Regen Prompt", "Regen Image"
        ])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(3, 200)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 100)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        
        table_layout.addWidget(self.table)
        content_layout.addLayout(table_layout, 2)
        
        layout.addLayout(content_layout)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        # Workflow loading section
        self.load_workflow_batch_btn = QPushButton("📂 Load Workflow")
        self.load_workflow_batch_btn.clicked.connect(self.load_batch_workflow)
        button_layout.addWidget(self.load_workflow_batch_btn)
        
        self.workflow_filename_label = QLabel("Using parent workflow")
        self.workflow_filename_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        self.workflow_filename_label.setMinimumWidth(200)
        button_layout.addWidget(self.workflow_filename_label)
        
        button_layout.addSpacing(20)
        
        # Image size controls
        size_label = QLabel("Image Size:")
        button_layout.addWidget(size_label)
        
        self.batch_size_combo = QComboBox()
        self.batch_size_presets = {
            "512x512": (512, 512),
            "768x768": (768, 768),
            "1024x1024": (1024, 1024),
            "512x768": (512, 768),
            "768x1024": (768, 1024),
            "768x512": (768, 512),
            "1024x768": (1024, 768),
            "1024x576": (1024, 576),
            "576x1024": (576, 1024),
        }
        self.batch_size_combo.addItems(self.batch_size_presets.keys())
        self.batch_size_combo.setCurrentText("512x512")
        self.batch_size_combo.currentTextChanged.connect(self.on_batch_size_changed)
        button_layout.addWidget(self.batch_size_combo)
        
        aspect_label = QLabel("Aspect:")
        button_layout.addWidget(aspect_label)
        
        self.batch_aspect_combo = QComboBox()
        self.batch_aspect_ratios = {
            "1:1": (1, 1),
            "4:3": (4, 3),
            "3:4": (3, 4),
            "16:9": (16, 9),
            "9:16": (9, 16),
            "3:2": (3, 2),
            "2:3": (2, 3),
        }
        self.batch_aspect_combo.addItems(self.batch_aspect_ratios.keys())
        self.batch_aspect_combo.setCurrentText("1:1")
        self.batch_aspect_combo.currentTextChanged.connect(self.on_batch_aspect_changed)
        button_layout.addWidget(self.batch_aspect_combo)
        
        base_size_label = QLabel("Base:")
        button_layout.addWidget(base_size_label)
        
        self.batch_base_size_combo = QComboBox()
        self.batch_base_size_combo.addItems(["512", "768", "1024"])
        self.batch_base_size_combo.setCurrentText("512")
        self.batch_base_size_combo.currentTextChanged.connect(self.on_batch_aspect_changed)
        button_layout.addWidget(self.batch_base_size_combo)
        
        # Current dimensions display
        self.batch_dimensions_label = QLabel("512x512")
        self.batch_dimensions_label.setStyleSheet("QLabel { color: #0066cc; font-weight: bold; }")
        button_layout.addWidget(self.batch_dimensions_label)
        
        button_layout.addSpacing(20)
        
        self.process_batch_btn = QPushButton("🎨 Process Batch (Generate Images)")
        self.process_batch_btn.clicked.connect(self.process_batch)
        button_layout.addWidget(self.process_batch_btn)
        
        self.save_csv_btn = QPushButton("💾 Save CSV")
        self.save_csv_btn.clicked.connect(self.save_csv)
        button_layout.addWidget(self.save_csv_btn)
        
        self.save_images_btn = QPushButton("💾 Save All Images")
        self.save_images_btn.clicked.connect(self.save_all_images)
        button_layout.addWidget(self.save_images_btn)
        
        self.save_zip_btn = QPushButton("📦 Save All as Zip")
        self.save_zip_btn.clicked.connect(self.save_all_as_zip)
        button_layout.addWidget(self.save_zip_btn)
        
        self.exit_batch_btn = QPushButton("❌ Exit")
        self.exit_batch_btn.clicked.connect(self.close)
        button_layout.addWidget(self.exit_batch_btn)
        
        button_layout.addStretch()
        
        # Status indicator
        self.status_indicator = QLabel("⚪ Ready")
        self.status_indicator.setStyleSheet("QLabel { font-weight: bold; }")
        button_layout.addWidget(self.status_indicator)
        
        # Progress label
        self.progress_label = QLabel("0 / 0")
        button_layout.addWidget(self.progress_label)
        
        layout.addLayout(button_layout)
        
        # Status text box
        status_box_label = QLabel("Status Messages:")
        layout.addWidget(status_box_label)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(80)
        layout.addWidget(self.status_text)
        
        self.log_status("Ready. Load a CSV/text file to begin.")
    
    def log_status(self, message):
        """Add status message"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{timestamp}] {message}")
        cursor = self.status_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.status_text.setTextCursor(cursor)
    
    def log_error(self, message):
        """Add error message"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f'<span style="color: red;">[{timestamp}] ERROR: {message}</span>')
        cursor = self.status_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.status_text.setTextCursor(cursor)
    
    def set_busy(self, is_busy):
        """Update status indicator"""
        if is_busy:
            self.status_indicator.setText("🔴 Busy")
            self.status_indicator.setStyleSheet("QLabel { font-weight: bold; color: red; }")
        else:
            self.status_indicator.setText("🟢 Done")
            self.status_indicator.setStyleSheet("QLabel { font-weight: bold; color: green; }")
    
    def get_delimiter(self):
        """Get selected delimiter"""
        delim_map = {
            "Comma (,)": ",",
            "Tab": "\t",
            "Semicolon (;)": ";",
            "Pipe (|)": "|"
        }
        return delim_map.get(self.delimiter_combo.currentText(), ",")
    
    def load_file(self):
        """Load CSV or text file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*.*)"
        )
        
        if file_path:
            try:
                self.loaded_file_path = file_path  # Store for default save name
                delimiter = self.get_delimiter()
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    data = list(reader)
                
                if data:
                    self.populate_table(data)
                    filename = Path(file_path).name
                    self.loaded_file_label.setText(f"Loaded: {filename}")
                    self.log_status(f"✓ Loaded {len(data)} rows from {filename}")
                else:
                    self.log_error("File is empty")
                    
            except Exception as e:
                self.log_error(f"Failed to load file: {str(e)}")
    
    def populate_table(self, data):
        """Populate table with loaded data"""
        self.table.setRowCount(len(data))
        
        for row_idx, row_data in enumerate(data):
            # Column 0: Phrase
            phrase = row_data[0] if len(row_data) > 0 else ""
            self.table.setItem(row_idx, 0, QTableWidgetItem(phrase))
            
            # Column 1: Description
            desc = row_data[1] if len(row_data) > 1 else ""
            self.table.setItem(row_idx, 1, QTableWidgetItem(desc))
            
            # Column 2: Prompt
            prompt = row_data[2] if len(row_data) > 2 else ""
            self.table.setItem(row_idx, 2, QTableWidgetItem(prompt))
            
            # Column 3: Filename (auto-generate if empty)
            if len(row_data) > 3 and row_data[3]:
                filename = row_data[3]
            else:
                filename = self.generate_filename(phrase, row_idx)
            self.table.setItem(row_idx, 3, QTableWidgetItem(filename))
            
            # Column 4: Regen Prompt button
            regen_prompt_btn = QPushButton("🔄")
            regen_prompt_btn.clicked.connect(lambda checked, r=row_idx: self.regenerate_single_prompt(r))
            self.table.setCellWidget(row_idx, 4, regen_prompt_btn)
            
            # Column 5: Regen Image button
            regen_image_btn = QPushButton("🎨")
            regen_image_btn.clicked.connect(lambda checked, r=row_idx: self.regenerate_single_image(r))
            self.table.setCellWidget(row_idx, 5, regen_image_btn)
    
    def generate_filename(self, phrase, index):
        """Generate filename from phrase and index"""
        clean_phrase = re.sub(r'[^\w\s-]', '', phrase)
        clean_phrase = re.sub(r'[-\s]+', '_', clean_phrase).strip('_')
        clean_phrase = clean_phrase[:30]  # Limit length
        return f"{clean_phrase}_{index+1:04d}"
    
    def generate_all_prompts(self):
        """Generate prompts for all rows using batch processing"""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "Please load a file first!")
            return
        
        if not self.parent_window:
            QMessageBox.warning(self, "Error", "Parent window not available!")
            return
        
        model = self.batch_ollama_combo.currentText()
        if model in ["(No models available)", "(Ollama not running)"]:
            QMessageBox.warning(self, "No Model", "Please select a valid Ollama model!")
            return
        
        # Collect batch data
        batch_data = []
        for row in range(self.table.rowCount()):
            phrase = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
            desc = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
            if phrase:
                batch_data.append((phrase, desc))
        
        if not batch_data:
            QMessageBox.warning(self, "No Data", "No phrases to process!")
            return
        
        self.set_busy(True)
        self.gen_prompts_btn.setEnabled(False)
        
        # Start batch prompt generation
        self.batch_prompt_gen = BatchPromptGenerator(batch_data, model)
        self.batch_prompt_gen.status.connect(self.log_status)
        self.batch_prompt_gen.error.connect(self.log_error)
        self.batch_prompt_gen.progress.connect(self.update_progress)
        self.batch_prompt_gen.finished.connect(self.on_batch_prompts_generated)
        self.batch_prompt_gen.start()
    
    def on_batch_prompts_generated(self, prompts):
        """Handle batch prompt generation completion"""
        self.gen_prompts_btn.setEnabled(True)
        self.set_busy(False)
        
        # Update table with generated prompts
        for row_idx, prompt in enumerate(prompts):
            if row_idx < self.table.rowCount():
                self.table.setItem(row_idx, 2, QTableWidgetItem(prompt))
        
        self.log_status(f"✓ Generated {len(prompts)} prompts")
    
    def regenerate_single_prompt(self, row):
        """Regenerate prompt for a single row"""
        phrase = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
        desc = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        
        if not phrase:
            QMessageBox.warning(self, "No Phrase", "Please enter a phrase first!")
            return
        
        model = self.parent_window.ollama_model_combo.currentText()
        if model in ["(No models available)", "(Ollama not running)"]:
            QMessageBox.warning(self, "No Model", "Please select a valid Ollama model!")
            return
        
        self.log_status(f"Regenerating prompt for row {row + 1}...")
        
        # Use single prompt generator
        prompt_gen = OllamaPromptGenerator(f"{phrase}. {desc}".strip(), model)
        prompt_gen.finished.connect(lambda p, r=row: self.on_single_prompt_generated(r, p))
        prompt_gen.error.connect(self.log_error)
        
        # Keep reference to prevent garbage collection
        self.active_workers.append(prompt_gen)
        prompt_gen.finished.connect(lambda: self.cleanup_worker(prompt_gen))
        
        prompt_gen.start()
    
    def on_single_prompt_generated(self, row, prompt):
        """Handle single prompt generation"""
        if prompt:
            self.table.setItem(row, 2, QTableWidgetItem(prompt))
            self.log_status(f"✓ Prompt regenerated for row {row + 1}")
    
    def regenerate_single_image(self, row):
        """Regenerate image for a single row"""
        prompt = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
        filename = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
        
        if not prompt:
            QMessageBox.warning(self, "No Prompt", "Please generate a prompt first!")
            return
        
        self.log_status(f"Generating image for row {row + 1}: {filename}")
        
        # Get dimensions from batch controls
        width, height = self.get_batch_dimensions()
        
        # Use batch-specific workflow if loaded, otherwise use parent's
        custom_workflow = self.batch_custom_workflow if self.batch_custom_workflow else self.parent_window.custom_workflow
        
        # Generate single image
        worker = WorkflowRunner(
            prompt, 
            width=width, 
            height=height,
            custom_workflow=custom_workflow
        )
        worker.finished.connect(lambda img, r=row: self.on_single_image_generated(r, img))
        worker.error.connect(self.log_error)
        
        # Keep reference to prevent garbage collection
        self.active_workers.append(worker)
        worker.finished.connect(lambda: self.cleanup_worker(worker))
        
        worker.start()
    
    def on_single_image_generated(self, row, image_data):
        """Handle single image generation"""
        if image_data:
            self.image_data[row] = image_data
            self.log_status(f"✓ Image generated for row {row + 1}")
            
            # Update preview if this row is selected
            if self.current_selected_row == row:
                self.display_preview_image(image_data)
    
    def cleanup_worker(self, worker):
        """Remove worker from active list after completion"""
        try:
            if worker in self.active_workers:
                self.active_workers.remove(worker)
            # Wait for thread to finish properly
            if worker.isRunning():
                worker.wait(1000)  # Wait up to 1 second
        except Exception as e:
            pass  # Ignore cleanup errors
    
    def closeEvent(self, event):
        """Clean up threads when dialog closes"""
        # Wait for all active workers to finish
        for worker in self.active_workers:
            if worker.isRunning():
                worker.quit()
                worker.wait(2000)  # Wait up to 2 seconds
        
        # Clean up batch workers if running
        if hasattr(self, 'batch_prompt_gen') and self.batch_prompt_gen.isRunning():
            self.batch_prompt_gen.quit()
            self.batch_prompt_gen.wait(2000)
        
        if hasattr(self, 'batch_img_gen') and self.batch_img_gen.isRunning():
            self.batch_img_gen.quit()
            self.batch_img_gen.wait(2000)
        
        event.accept()
    
    def process_batch(self):
        """Process entire batch to generate all images"""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "Please load a file first!")
            return
        
        # Collect batch items
        batch_items = []
        for row in range(self.table.rowCount()):
            prompt = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
            filename = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
            
            if prompt:
                batch_items.append((prompt, filename))
        
        if not batch_items:
            QMessageBox.warning(self, "No Prompts", "Please generate prompts first!")
            return
        
        self.set_busy(True)
        self.process_batch_btn.setEnabled(False)
        
        # Get dimensions from batch controls
        width, height = self.get_batch_dimensions()
        
        # Use batch-specific workflow if loaded, otherwise use parent's
        custom_workflow = self.batch_custom_workflow if self.batch_custom_workflow else self.parent_window.custom_workflow
        
        # Log batch settings
        self.log_status(f"Starting batch with size {width}x{height}")
        
        # Start batch image generation
        self.batch_img_gen = BatchImageGenerator(batch_items, width, height, custom_workflow)
        self.batch_img_gen.status.connect(self.log_status)
        self.batch_img_gen.error.connect(self.log_error)
        self.batch_img_gen.progress.connect(self.update_progress)
        self.batch_img_gen.image_generated.connect(self.on_batch_image_generated)
        self.batch_img_gen.finished.connect(self.on_batch_processing_complete)
        self.batch_img_gen.start()
    
    def on_batch_image_generated(self, row_idx, image_data):
        """Handle individual image generation in batch"""
        if image_data:
            self.image_data[row_idx] = image_data
    
    def on_batch_processing_complete(self):
        """Handle batch processing completion"""
        self.process_batch_btn.setEnabled(True)
        self.set_busy(False)
        self.log_status(f"✓ Batch processing complete! Generated {len(self.image_data)} images")
    
    def update_progress(self, current, total):
        """Update progress display"""
        self.progress_label.setText(f"{current} / {total}")
    
    def on_row_selected(self):
        """Handle row selection to show image preview"""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            self.current_selected_row = row
            
            if row in self.image_data:
                self.display_preview_image(self.image_data[row])
            else:
                self.preview_image_label.setText("No image generated yet")
    
    def display_preview_image(self, image_data):
        """Display image in preview area"""
        try:
            image = Image.open(io.BytesIO(image_data))
            
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            qimage = QImage.fromData(img_byte_arr.read())
            pixmap = QPixmap.fromImage(qimage)
            
            scaled_pixmap = pixmap.scaled(
                380, 380,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.preview_image_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self.log_error(f"Failed to display preview: {str(e)}")
    
    def load_batch_workflow(self):
        """Load a custom workflow for batch processing"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load ComfyUI Workflow for Batch",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    workflow_data = json.load(f)
                
                # Validate workflow
                if 'nodes' in workflow_data or 'prompt' in workflow_data or any(isinstance(v, dict) for v in workflow_data.values()):
                    self.batch_custom_workflow = workflow_data
                    self.batch_workflow_path = file_path
                    filename = Path(file_path).name
                    self.workflow_filename_label.setText(f"{filename}")
                    self.workflow_filename_label.setStyleSheet("QLabel { color: #0066cc; font-weight: bold; }")
                    self.log_status(f"✓ Batch workflow loaded: {filename}")
                else:
                    self.log_error("Invalid workflow format")
                    
            except Exception as e:
                self.log_error(f"Failed to load workflow: {str(e)}")
    
    def on_batch_size_changed(self, size_text):
        """Handle batch size preset selection"""
        if size_text in self.batch_size_presets:
            width, height = self.batch_size_presets[size_text]
            self.batch_dimensions_label.setText(f"{width}x{height}")
            
            # Disable aspect ratio controls when using presets
            self.batch_aspect_combo.setEnabled(False)
            self.batch_base_size_combo.setEnabled(False)
    
    def on_batch_aspect_changed(self):
        """Handle batch aspect ratio selection"""
        aspect_text = self.batch_aspect_combo.currentText()
        base_size = int(self.batch_base_size_combo.currentText())
        
        if aspect_text in self.batch_aspect_ratios:
            ratio_w, ratio_h = self.batch_aspect_ratios[aspect_text]
            
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
            
            self.batch_dimensions_label.setText(f"{width}x{height}")
            
            # Enable aspect ratio controls
            self.batch_aspect_combo.setEnabled(True)
            self.batch_base_size_combo.setEnabled(True)
            
            # Update size combo to show it's custom
            self.batch_size_combo.blockSignals(True)
            self.batch_size_combo.setCurrentIndex(-1)
            self.batch_size_combo.blockSignals(False)
    
    def get_batch_dimensions(self):
        """Get image dimensions from batch mode controls"""
        # Parse from dimensions label
        dims_text = self.batch_dimensions_label.text()
        try:
            parts = dims_text.split('x')
            if len(parts) == 2:
                width = int(parts[0])
                height = int(parts[1])
                return (width, height)
        except:
            pass
        
        # Fallback to default
        return (512, 512)
    
    def save_csv(self):
        """Save updated CSV file to Output subdirectory with original filename"""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No data to save!")
            return
        
        # Determine default filename and location
        if self.loaded_file_path:
            original_name = Path(self.loaded_file_path).stem
            default_filename = f"{original_name}.csv"
        else:
            default_filename = "batch_output.csv"
        
        # Create Output subdirectory path
        output_dir = Path.cwd() / "Output"
        output_dir.mkdir(exist_ok=True)
        default_path = output_dir / default_filename
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV File",
            str(default_path),
            "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                delimiter = self.get_delimiter()
                
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, delimiter=delimiter)
                    
                    for row in range(self.table.rowCount()):
                        row_data = []
                        for col in range(4):  # Only save first 4 columns
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                
                self.log_status(f"✓ CSV saved to {file_path}")
                QMessageBox.information(self, "Success", f"CSV saved to:\n{file_path}")
                
            except Exception as e:
                self.log_error(f"Failed to save CSV: {str(e)}")
    
    def save_all_images(self):
        """Save all generated images to output directory"""
        if not self.image_data:
            QMessageBox.warning(self, "No Images", "No images to save!")
            return
        
        # Default to Output subdirectory
        output_dir = Path.cwd() / "Output"
        
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(output_dir)
        )
        
        if selected_dir:
            try:
                output_path = Path(selected_dir) / "Output"
                output_path.mkdir(exist_ok=True)
                
                saved_count = 0
                for row_idx, image_data in self.image_data.items():
                    filename = self.table.item(row_idx, 3).text() if self.table.item(row_idx, 3) else f"image_{row_idx:04d}"
                    
                    if not filename.endswith('.jpg'):
                        filename += '.jpg'
                    
                    file_path = output_path / filename
                    
                    # Save image
                    image = Image.open(io.BytesIO(image_data))
                    
                    if image.mode in ('RGBA', 'LA', 'P'):
                        rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                        if image.mode == 'P':
                            image = image.convert('RGBA')
                        rgb_image.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                        image = rgb_image
                    
                    image.save(file_path, 'JPEG', quality=95)
                    saved_count += 1
                
                self.log_status(f"✓ Saved {saved_count} images to {output_path}")
                QMessageBox.information(self, "Success", f"Saved {saved_count} images to:\n{output_path}")
                
            except Exception as e:
                self.log_error(f"Failed to save images: {str(e)}")
    
    def save_all_as_zip(self):
        """Save all images and CSV to a zip file in Output subdirectory"""
        if not self.image_data and self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No images or data to save!")
            return
        
        try:
            import zipfile
            from datetime import datetime
            
            # Determine default filename
            if self.loaded_file_path:
                original_name = Path(self.loaded_file_path).stem
                default_filename = f"{original_name}_batch.zip"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_filename = f"batch_output_{timestamp}.zip"
            
            # Create Output subdirectory
            output_dir = Path.cwd() / "Output"
            output_dir.mkdir(exist_ok=True)
            default_path = output_dir / default_filename
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Batch as Zip",
                str(default_path),
                "Zip Files (*.zip)"
            )
            
            if file_path:
                with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Save CSV data
                    csv_data = io.StringIO()
                    delimiter = self.get_delimiter()
                    writer = csv.writer(csv_data, delimiter=delimiter)
                    
                    for row in range(self.table.rowCount()):
                        row_data = []
                        for col in range(4):
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
                    
                    # Add CSV to zip
                    csv_filename = "batch_data.csv"
                    zipf.writestr(csv_filename, csv_data.getvalue())
                    
                    # Save all images
                    saved_count = 0
                    for row_idx, image_data in self.image_data.items():
                        filename = self.table.item(row_idx, 3).text() if self.table.item(row_idx, 3) else f"image_{row_idx:04d}"
                        
                        if not filename.endswith('.jpg'):
                            filename += '.jpg'
                        
                        # Convert image
                        image = Image.open(io.BytesIO(image_data))
                        
                        if image.mode in ('RGBA', 'LA', 'P'):
                            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                            if image.mode == 'P':
                                image = image.convert('RGBA')
                            rgb_image.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                            image = rgb_image
                        
                        # Save to bytes
                        img_byte_arr = io.BytesIO()
                        image.save(img_byte_arr, format='JPEG', quality=95)
                        img_byte_arr.seek(0)
                        
                        # Add to zip
                        zipf.writestr(f"images/{filename}", img_byte_arr.getvalue())
                        saved_count += 1
                    
                    self.log_status(f"✓ Saved {saved_count} images and CSV to zip: {file_path}")
                    QMessageBox.information(
                        self, 
                        "Success", 
                        f"Saved batch to zip file:\n{file_path}\n\nContents:\n- CSV file\n- {saved_count} images"
                    )
                
        except Exception as e:
            self.log_error(f"Failed to create zip file: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to create zip file:\n{str(e)}")


class OllamaPromptGenerator(QThread):
    """Thread to generate prompts using Ollama"""
    finished = pyqtSignal(str)  # Emits generated prompt
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, phrase, model, ollama_url="http://127.0.0.1:11434"):
        super().__init__()
        self.phrase = phrase
        self.model = model
        self.ollama_url = ollama_url
    
    def run(self):
        """Generate prompt using Ollama"""
        try:
            self.status.emit(f"Generating prompt with {self.model}...")
            
            system_prompt = """You are an expert at creating detailed image generation prompts. 
Given a simple word or phrase, expand it into a detailed, vivid prompt suitable for an AI image generator.
Include details about: style, composition, lighting, mood, colors, and technical aspects.
Keep the prompt under 300 words and make it descriptive and creative.
Only return the image prompt, nothing else."""

            user_prompt = f"Create a detailed image generation prompt based on this concept: {self.phrase}"
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "stream": False
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_prompt = result.get('response', '').strip()
                
                if generated_prompt:
                    self.status.emit("✓ Prompt generated successfully!")
                    self.finished.emit(generated_prompt)
                else:
                    self.error.emit("Empty response from Ollama")
                    self.finished.emit("")
            else:
                self.error.emit(f"Ollama error: {response.status_code} - {response.text}")
                self.finished.emit("")
                
        except requests.exceptions.ConnectionError:
            self.error.emit("Cannot connect to Ollama. Is it running at http://127.0.0.1:11434?")
            self.finished.emit("")
        except Exception as e:
            self.error.emit(f"Error generating prompt: {str(e)}")
            self.finished.emit("")


class WorkflowRunner(QThread):
    """Thread to run ComfyUI workflow without blocking UI"""
    finished = pyqtSignal(object)  # Emits image data or None
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    
    def __init__(self, prompt_text, server_address="127.0.0.1:8188", seed=None, width=512, height=512, custom_workflow=None):
        super().__init__()
        self.prompt_text = prompt_text
        self.server_address = server_address
        self.workflow = None
        self.seed = seed
        self.width = width
        self.height = height
        self.custom_workflow = custom_workflow  # Custom workflow data if provided
        
    def load_workflow(self, width=512, height=512):
        """Load and modify the workflow with the new prompt"""
        import random
        
        # Generate random seed if not provided
        if self.seed is None:
            self.seed = random.randint(0, 2**32 - 1)
        
        # If custom workflow is provided, use it
        if self.custom_workflow:
            # Try to intelligently update the custom workflow
            return self.update_custom_workflow(self.custom_workflow, width, height)
        
        # Default Z-Image Turbo workflow
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
    
    def update_custom_workflow(self, workflow_data, width, height):
        """Update custom workflow with current parameters"""
        # Make a deep copy to avoid modifying original
        import copy
        workflow = copy.deepcopy(workflow_data)
        
        # Try to find and update common node types
        # This is a best-effort approach for custom workflows
        
        if 'nodes' in workflow:
            # Full workflow format with UI data - extract prompt
            nodes = workflow.get('nodes', [])
            definitions = workflow.get('definitions', {})
            subgraphs = definitions.get('subgraphs', []) if definitions else []
            
            prompt_dict = {}
            
            # List of UI-only nodes that shouldn't be in the prompt
            ui_only_nodes = [
                'Note', 'MarkdownNote', 'PrimitiveNode', 'Reroute',
                'JunctionNode', 'PreviewImage', 'LoadImageMask'
            ]
            
            for node in nodes:
                node_id = str(node.get('id', ''))
                node_type = node.get('type', '')
                
                # Skip UI-only nodes
                if node_type in ui_only_nodes:
                    continue
                
                # Check if this is a subgraph node (UUID format)
                if len(node_type) > 30 and '-' in node_type:
                    # This is a subgraph reference - skip it for now
                    # The workflow should still work with the base nodes
                    self.status.emit(f"Skipping subgraph node: {node_id}")
                    continue
                
                # Create simplified prompt structure
                if node_type and 'inputs' in node:
                    # Get inputs, filtering out UI elements
                    inputs = {}
                    node_inputs = node.get('inputs', [])
                    
                    # Handle both list and dict input formats
                    if isinstance(node_inputs, list):
                        # List format from UI - extract actual input values
                        for inp in node_inputs:
                            if isinstance(inp, dict):
                                name = inp.get('name')
                                # Check if there's a link or widget value
                                if 'link' in inp and inp['link'] is not None:
                                    # This is a connection, need to find the link
                                    inputs[name] = None  # Will be set by links
                    else:
                        # Already in dict format
                        inputs = node_inputs
                    
                    # Get widget values if present
                    widgets = node.get('widgets_values', [])
                    
                    # Map widgets to inputs based on common patterns
                    if node_type == 'CLIPTextEncode' and widgets:
                        inputs['text'] = widgets[0] if widgets else ""
                    elif node_type == 'TextEncodeQwenImageEditPlus' and widgets:
                        # Qwen custom node uses 'prompt' instead of 'text'
                        inputs['prompt'] = widgets[0] if widgets else ""
                    elif node_type == 'KSampler' and len(widgets) >= 6:
                        inputs['seed'] = widgets[0]
                        inputs['steps'] = widgets[2]
                        inputs['cfg'] = widgets[3]
                        inputs['sampler_name'] = widgets[4]
                        inputs['scheduler'] = widgets[5]
                        inputs['denoise'] = widgets[6] if len(widgets) > 6 else 1.0
                    elif node_type in ['EmptyLatentImage', 'EmptySD3LatentImage'] and len(widgets) >= 2:
                        inputs['width'] = widgets[0]
                        inputs['height'] = widgets[1]
                        inputs['batch_size'] = widgets[2] if len(widgets) > 2 else 1
                    elif node_type == 'CheckpointLoaderSimple' and widgets:
                        inputs['ckpt_name'] = widgets[0]
                    elif node_type == 'SaveImage' and widgets:
                        inputs['filename_prefix'] = widgets[0] if widgets else "ComfyUI"
                    elif node_type == 'ModelSamplingAuraFlow' and widgets:
                        inputs['shift'] = widgets[0] if widgets else 4.0
                    elif node_type == 'ModelSamplingFlux' and widgets:
                        inputs['max_shift'] = widgets[0] if widgets else 1.15
                        inputs['base_shift'] = widgets[1] if len(widgets) > 1 else 0.5
                        inputs['width'] = widgets[2] if len(widgets) > 2 else 1024
                        inputs['height'] = widgets[3] if len(widgets) > 3 else 1024
                    
                    prompt_dict[node_id] = {
                        'inputs': inputs,
                        'class_type': node_type
                    }
            
            # Now process links to set up connections
            links = workflow.get('links', [])
            for link in links:
                if len(link) >= 6:
                    # link format: [id, source_node, source_slot, target_node, target_slot, type]
                    source_node = str(link[1])
                    source_slot = link[2]
                    target_node = str(link[3])
                    target_slot = link[4]
                    
                    # Find input name for target
                    if target_node in prompt_dict:
                        target_node_data = None
                        for node in nodes:
                            if str(node.get('id')) == target_node:
                                target_node_data = node
                                break
                        
                        if target_node_data:
                            target_inputs = target_node_data.get('inputs', [])
                            if isinstance(target_inputs, list) and target_slot < len(target_inputs):
                                input_name = target_inputs[target_slot].get('name')
                                if input_name:
                                    # Set the connection
                                    prompt_dict[target_node]['inputs'][input_name] = [source_node, source_slot]
            
            # Try to update text, seed, and dimensions in the extracted prompt
            self.update_workflow_params(prompt_dict, width, height)
            return prompt_dict
            
        else:
            # Already in prompt format
            self.update_workflow_params(workflow, width, height)
            return workflow
    
    def expand_subgraph(self, parent_node, subgraph_id, subgraphs):
        """Expand a subgraph node into its component nodes"""
        try:
            # Find the subgraph definition
            subgraph_def = None
            for sg in subgraphs:
                if sg.get('id') == subgraph_id:
                    subgraph_def = sg
                    break
            
            if not subgraph_def:
                return None
            
            # Get the nodes from the subgraph
            sg_nodes = subgraph_def.get('nodes', [])
            result = {}
            
            # For text encoding subgraphs, look for CLIPTextEncode nodes
            for sg_node in sg_nodes:
                node_type = sg_node.get('type', '')
                node_id = str(sg_node.get('id', ''))
                
                if node_type == 'CLIPTextEncode':
                    # This is the main text encode node
                    inputs = {}
                    widgets = sg_node.get('widgets_values', [])
                    
                    # Get text from parent node's widgets if available
                    parent_widgets = parent_node.get('widgets_values', [])
                    if parent_widgets:
                        inputs['text'] = parent_widgets[0] if parent_widgets else ""
                    elif widgets:
                        inputs['text'] = widgets[0] if widgets else ""
                    
                    result[node_id] = {
                        'inputs': inputs,
                        'class_type': 'CLIPTextEncode'
                    }
            
            return result if result else None
            
        except Exception as e:
            return None
    
    def update_workflow_params(self, workflow, width, height):
        """Update workflow parameters (prompt, seed, dimensions)"""
        for node_id, node_data in workflow.items():
            if not isinstance(node_data, dict):
                continue
                
            inputs = node_data.get('inputs', {})
            class_type = node_data.get('class_type', '')
            
            # Update positive text prompts (look for common naming patterns)
            # Handle different text input field names
            text_encode_nodes = [
                'CLIPTextEncode', 
                'CLIPTextEncodeSDXL', 
                'TextEncodeQwenImageEditPlus',
                'CLIPTextEncodeFlux',
                'ConditioningSetArea'
            ]
            
            if class_type in text_encode_nodes:
                # Try different field names
                text_field = None
                if 'text' in inputs:
                    text_field = 'text'
                elif 'prompt' in inputs:
                    text_field = 'prompt'
                elif 'string' in inputs:
                    text_field = 'string'
                
                if text_field:
                    # Check if this is likely the positive prompt
                    current_text = inputs.get(text_field, '')
                    if isinstance(current_text, str):
                        # Only update if it seems like a positive prompt
                        if not any(neg_word in str(current_text).lower()[:100] 
                                  for neg_word in ['negative', 'worst', 'ugly', 'bad', 'watermark', 'text,']):
                            inputs[text_field] = self.prompt_text
            
            # Update seed
            if 'seed' in inputs and isinstance(inputs['seed'], int):
                inputs['seed'] = self.seed
            
            # Update dimensions
            if class_type in ['EmptyLatentImage', 'EmptySD3LatentImage']:
                if 'width' in inputs:
                    inputs['width'] = width
                if 'height' in inputs:
                    inputs['height'] = height
    
    def run(self):
        """Execute the workflow"""
        try:
            self.status.emit("Loading workflow...")
            workflow = self.load_workflow(self.width, self.height)
            
            self.status.emit("Queuing prompt to ComfyUI...")
            prompt_data = {"prompt": workflow}
            
            # Debug: Log the workflow structure
            import json
            self.status.emit(f"Sending workflow with {len(workflow)} nodes")
            
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
            
            # Check for immediate errors
            if 'error' in result:
                self.error.emit(f"ComfyUI error: {result['error']}")
                self.finished.emit(None)
                return
            
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
            import traceback
            self.error.emit(f"Traceback: {traceback.format_exc()}")
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
                        
                        # Look for any SaveImage node output (try all node IDs)
                        for node_id, node_output in outputs.items():
                            if 'images' in node_output:
                                images = node_output['images']
                                if images:
                                    image_info = images[0]
                                    filename = image_info['filename']
                                    subfolder = image_info.get('subfolder', '')
                                    image_type = image_info.get('type', 'output')
                                    
                                    # Download the image
                                    self.status.emit(f"Downloading generated image: {filename}")
                                    return self.download_image(filename, subfolder, image_type)
                        
                        # If we got here, the prompt finished but no images found
                        # Check if there was an error
                        status = history[prompt_id].get('status', {})
                        if status.get('completed', False) and not outputs:
                            self.error.emit("Workflow completed but produced no images")
                            return None
                
                time.sleep(2)  # Wait 2 seconds before checking again
                
            except Exception as e:
                self.status.emit(f"Polling error: {str(e)}")
                time.sleep(2)
        
        self.error.emit("Timeout waiting for image generation")
        return None
    
    def download_image(self, filename, subfolder='', image_type='output'):
        """Download the generated image from ComfyUI"""
        try:
            params = {
                'filename': filename,
                'type': image_type
            }
            if subfolder:
                params['subfolder'] = subfolder
            
            response = requests.get(
                f"http://{self.server_address}/view",
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.content
            else:
                self.error.emit(f"Failed to download image: HTTP {response.status_code}")
            
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
        self.current_phrase = ""
        self.image_counter = {}  # Track counters per phrase
        self.active_worker = None  # Track active worker thread
        self.custom_workflow = None  # Store loaded custom workflow
        self.workflow_loaded = False
        self.server_address = "127.0.0.1:8188"
        
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
        self.setGeometry(100, 100, 900, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Prompt Generation Section
        prompt_gen_group = QGroupBox("AI Prompt Generation (Ollama)")
        prompt_gen_layout = QVBoxLayout()
        
        # Phrase input
        phrase_layout = QHBoxLayout()
        phrase_label = QLabel("Concept/Phrase:")
        phrase_layout.addWidget(phrase_label)
        
        self.phrase_input = QLineEdit()
        self.phrase_input.setPlaceholderText("Enter a word or phrase (e.g., 'sunset over mountains', 'cyberpunk city')...")
        phrase_layout.addWidget(self.phrase_input)
        prompt_gen_layout.addLayout(phrase_layout)
        
        # Ollama controls
        ollama_controls_layout = QHBoxLayout()
        
        model_label = QLabel("Ollama Model:")
        ollama_controls_layout.addWidget(model_label)
        
        self.ollama_model_combo = QComboBox()
        self.ollama_model_combo.setMinimumWidth(200)
        ollama_controls_layout.addWidget(self.ollama_model_combo)
        
        self.refresh_models_btn = QPushButton("🔄 Update Models")
        self.refresh_models_btn.clicked.connect(self.refresh_ollama_models)
        ollama_controls_layout.addWidget(self.refresh_models_btn)
        
        self.generate_prompt_btn = QPushButton("✨ Generate Prompt")
        self.generate_prompt_btn.clicked.connect(self.generate_prompt_from_phrase)
        ollama_controls_layout.addWidget(self.generate_prompt_btn)
        
        ollama_controls_layout.addStretch()
        
        prompt_gen_layout.addLayout(ollama_controls_layout)
        prompt_gen_group.setLayout(prompt_gen_layout)
        layout.addWidget(prompt_gen_group)
        
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
        
        # Workflow Selection Section
        workflow_section = QGroupBox("ComfyUI Workflow Configuration")
        workflow_layout = QHBoxLayout()
        
        workflow_label = QLabel("Workflow File:")
        workflow_layout.addWidget(workflow_label)
        
        self.workflow_path_label = QLabel("Default Z-Image Turbo")
        self.workflow_path_label.setStyleSheet("QLabel { color: #666; font-style: italic; }")
        self.workflow_path_label.setMinimumWidth(200)
        workflow_layout.addWidget(self.workflow_path_label)
        
        self.load_workflow_btn = QPushButton("📂 Load Workflow")
        self.load_workflow_btn.clicked.connect(self.load_custom_workflow)
        workflow_layout.addWidget(self.load_workflow_btn)
        
        self.reset_workflow_btn = QPushButton("🔄 Reset to Default")
        self.reset_workflow_btn.clicked.connect(self.reset_to_default_workflow)
        workflow_layout.addWidget(self.reset_workflow_btn)
        
        workflow_layout.addStretch()
        
        # Server status indicator
        status_separator = QFrame()
        status_separator.setFrameShape(QFrame.Shape.VLine)
        status_separator.setFrameShadow(QFrame.Shadow.Sunken)
        workflow_layout.addWidget(status_separator)
        
        server_label = QLabel("ComfyUI Server:")
        workflow_layout.addWidget(server_label)
        
        self.server_status_label = QLabel("⚪ Checking...")
        self.server_status_label.setStyleSheet("QLabel { font-weight: bold; }")
        workflow_layout.addWidget(self.server_status_label)
        
        self.check_server_btn = QPushButton("🔍 Check")
        self.check_server_btn.clicked.connect(self.check_server_status)
        workflow_layout.addWidget(self.check_server_btn)
        
        # Workflow status indicator
        workflow_status_separator = QFrame()
        workflow_status_separator.setFrameShape(QFrame.Shape.VLine)
        workflow_status_separator.setFrameShadow(QFrame.Shadow.Sunken)
        workflow_layout.addWidget(workflow_status_separator)
        
        wf_status_label = QLabel("Workflow:")
        workflow_layout.addWidget(wf_status_label)
        
        self.workflow_status_label = QLabel("✓ Default Loaded")
        self.workflow_status_label.setStyleSheet("QLabel { font-weight: bold; color: green; }")
        workflow_layout.addWidget(self.workflow_status_label)
        
        workflow_section.setLayout(workflow_layout)
        layout.addWidget(workflow_section)
        
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
        
        self.batch_mode_btn = QPushButton("📊 Batch Mode")
        self.batch_mode_btn.clicked.connect(self.open_batch_mode)
        button_layout.addWidget(self.batch_mode_btn)
        
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
        
        # Load Ollama models on startup
        self.refresh_ollama_models()
        
        # Set default model to kimi-k2:1t-cloud if available
        QTimer.singleShot(1000, self.set_default_ollama_model)
        
        # Check server status on startup
        QTimer.singleShot(500, self.check_server_status)  # Check after 500ms
    
    def set_default_ollama_model(self):
        """Set default Ollama model to kimi-k2:1t-cloud"""
        target_model = "kimi-k2:1t-cloud"
        index = self.ollama_model_combo.findText(target_model)
        if index >= 0:
            self.ollama_model_combo.setCurrentIndex(index)
            self.log_status(f"✓ Default model set to {target_model}")
        else:
            self.log_status(f"⚠ Default model '{target_model}' not found. Using first available model.")
    
    def load_custom_workflow(self):
        """Load a custom ComfyUI workflow file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load ComfyUI Workflow",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        
        if file_path:
            filename = Path(file_path).name
            self.log_status(f"Loading workflow: {filename}")
            
            # Start workflow loader thread
            self.workflow_loader = WorkflowLoader(file_path, self.server_address)
            self.workflow_loader.finished.connect(self.on_workflow_loaded)
            self.workflow_loader.error.connect(self.log_error)
            self.workflow_loader.start()
    
    def on_workflow_loaded(self, success, message, workflow_data):
        """Handle workflow loading completion"""
        if success:
            self.custom_workflow = workflow_data
            self.workflow_loaded = True
            filename = Path(self.workflow_path_label.text()).name if "/" in self.workflow_path_label.text() or "\\" in self.workflow_path_label.text() else message
            self.workflow_path_label.setText(f"{filename}")
            self.workflow_path_label.setStyleSheet("QLabel { color: #0066cc; font-weight: bold; }")
            self.workflow_status_label.setText("✓ Custom Loaded")
            self.workflow_status_label.setStyleSheet("QLabel { font-weight: bold; color: green; }")
            self.log_status(f"✓ {message}")
        else:
            self.workflow_status_label.setText("✗ Load Failed")
            self.workflow_status_label.setStyleSheet("QLabel { font-weight: bold; color: red; }")
            self.log_error(message)
    
    def reset_to_default_workflow(self):
        """Reset to default Z-Image Turbo workflow"""
        self.custom_workflow = None
        self.workflow_loaded = False
        self.workflow_path_label.setText("Default Z-Image Turbo")
        self.workflow_status_label.setText("✓ Default Loaded")
        self.workflow_status_label.setStyleSheet("QLabel { font-weight: bold; color: green; }")
        self.log_status("✓ Reset to default Z-Image Turbo workflow")
    
    def check_server_status(self):
        """Check ComfyUI server status"""
        self.server_status_label.setText("⚪ Checking...")
        self.server_status_label.setStyleSheet("QLabel { font-weight: bold; }")
        
        # Start status checker thread
        self.status_checker = ServerStatusChecker(self.server_address)
        self.status_checker.status_update.connect(self.on_server_status_update)
        self.status_checker.start()
    
    def on_server_status_update(self, is_online, message):
        """Handle server status update"""
        if is_online:
            self.server_status_label.setText(f"🟢 {message}")
            self.server_status_label.setStyleSheet("QLabel { font-weight: bold; color: green; }")
            self.log_status(f"✓ ComfyUI server is {message}")
        else:
            self.server_status_label.setText(f"🔴 {message}")
            self.server_status_label.setStyleSheet("QLabel { font-weight: bold; color: red; }")
            self.log_error(f"ComfyUI server is {message}")
    
    def refresh_ollama_models(self):
        """Fetch available Ollama models"""
        try:
            self.log_status("Fetching Ollama models...")
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])
                
                self.ollama_model_combo.clear()
                
                if models:
                    for model in models:
                        model_name = model.get('name', '')
                        if model_name:
                            self.ollama_model_combo.addItem(model_name)
                    
                    self.log_status(f"✓ Found {len(models)} Ollama model(s)")
                else:
                    self.log_status("⚠ No Ollama models found. Pull models using: ollama pull <model_name>")
                    self.ollama_model_combo.addItem("(No models available)")
                    
            else:
                self.log_error(f"Failed to fetch Ollama models: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            self.log_error("Cannot connect to Ollama at http://127.0.0.1:11434. Is it running?")
            self.ollama_model_combo.clear()
            self.ollama_model_combo.addItem("(Ollama not running)")
        except Exception as e:
            self.log_error(f"Error fetching Ollama models: {str(e)}")
    
    def generate_prompt_from_phrase(self):
        """Generate detailed prompt from phrase using Ollama"""
        phrase = self.phrase_input.text().strip()
        
        if not phrase:
            QMessageBox.warning(self, "No Phrase", "Please enter a concept or phrase first!")
            return
        
        model = self.ollama_model_combo.currentText()
        
        if model in ["(No models available)", "(Ollama not running)"]:
            QMessageBox.warning(self, "No Model", "Please install Ollama models first!\n\nExample: ollama pull llama3.2")
            return
        
        # Store phrase for filename generation
        self.current_phrase = phrase
        
        # Disable button during generation
        self.generate_prompt_btn.setEnabled(False)
        
        # Clean up previous prompt generator if exists
        if hasattr(self, 'prompt_generator') and self.prompt_generator.isRunning():
            self.prompt_generator.quit()
            self.prompt_generator.wait(1000)
        
        # Create and start prompt generator thread
        self.prompt_generator = OllamaPromptGenerator(phrase, model)
        self.prompt_generator.status.connect(self.log_status)
        self.prompt_generator.error.connect(self.log_error)
        self.prompt_generator.finished.connect(self.on_prompt_generated)
        self.prompt_generator.start()
    
    def on_prompt_generated(self, prompt):
        """Handle generated prompt from Ollama"""
        self.generate_prompt_btn.setEnabled(True)
        
        if prompt:
            self.prompt_text.setText(prompt)
            self.log_status("✓ Prompt inserted into text box. Review and click 'Generate Image'.")
        else:
            self.log_error("Failed to generate prompt")
    
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
        # Clean up previous worker if exists
        if self.active_worker and self.active_worker.isRunning():
            self.active_worker.quit()
            self.active_worker.wait(1000)
        
        # Disable buttons during generation
        self.generate_btn.setEnabled(False)
        self.regenerate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        
        self.log_status(f"Starting image generation ({width}x{height})...")
        
        # Create and start worker thread with custom workflow if loaded
        self.active_worker = WorkflowRunner(
            prompt, 
            server_address=self.server_address,
            seed=seed, 
            width=width, 
            height=height,
            custom_workflow=self.custom_workflow
        )
        self.active_worker.status.connect(self.log_status)
        self.active_worker.error.connect(self.log_error)
        self.active_worker.finished.connect(self.on_generation_complete)
        self.active_worker.start()
    
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
                if hasattr(self.active_worker, 'seed'):
                    self.current_seed = self.active_worker.seed
                    self.log_status(f"✓ Image generation completed successfully! (Seed: {self.current_seed})")
                else:
                    self.log_status("✓ Image generation completed successfully!")
                
            except Exception as e:
                self.log_error(f"Failed to display image: {str(e)}")
        else:
            self.log_error("Image generation failed. Check error messages above.")
    
    def save_image(self):
        """Save the generated image as JPG with auto-naming"""
        if not self.current_image_data:
            QMessageBox.warning(self, "No Image", "No image to save!")
            return
        
        # Generate filename
        if self.current_phrase:
            # Clean phrase for filename
            clean_phrase = re.sub(r'[^\w\s-]', '', self.current_phrase)
            clean_phrase = re.sub(r'[-\s]+', '_', clean_phrase).strip('_')
            clean_phrase = clean_phrase[:50]  # Limit length
            
            # Get or increment counter for this phrase
            if clean_phrase not in self.image_counter:
                self.image_counter[clean_phrase] = 1
            else:
                self.image_counter[clean_phrase] += 1
            
            counter = self.image_counter[clean_phrase]
            default_filename = f"{clean_phrase}_{counter:04d}.jpg"
        else:
            default_filename = "generated_image_0001.jpg"
        
        # Open file dialog with auto-generated name
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            default_filename,
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
    
    def open_batch_mode(self):
        """Open batch mode dialog"""
        dialog = BatchModeDialog(self)
        dialog.exec()
    
    def closeEvent(self, event):
        """Clean up threads when main window closes"""
        # Wait for active worker to finish
        if self.active_worker and self.active_worker.isRunning():
            self.active_worker.quit()
            self.active_worker.wait(2000)
        
        # Wait for prompt generator to finish
        if hasattr(self, 'prompt_generator') and self.prompt_generator.isRunning():
            self.prompt_generator.quit()
            self.prompt_generator.wait(2000)
        
        event.accept()


def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = ComfyUIGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
