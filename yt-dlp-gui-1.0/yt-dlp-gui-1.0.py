#!/usr/bin/env python3

import sys
import os
import json
import re
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QTextEdit, QComboBox, QFileDialog, QGroupBox,
                            QCheckBox, QProgressBar, QMessageBox, QTabWidget,
                            QListWidget, QListWidgetItem, QSplitter, QTextBrowser)
from PyQt5.QtCore import QThread, pyqtSignal, QProcess, Qt, QUrl
from PyQt5.QtGui import QFont, QTextCursor, QPixmap, QDesktopServices
import subprocess

__version__ = "1.0.0"
__author__ = "Your Name"
__license__ = "MIT"

class DownloadThread(QThread):
    # Signals to communicate with main thread
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, urls, options):
        super().__init__()
        self.urls = urls if isinstance(urls, list) else [urls]
        self.options = options
        self.process = None
        self.is_cancelled = False
        
    def run(self):
        try:
            for i, url in enumerate(self.urls):
                if self.is_cancelled:
                    self.progress.emit("\n⚠️ Download cancelled by user\n")
                    break
                    
                self.progress.emit(f"\n📥 Downloading {i+1}/{len(self.urls)}: {url}\n")
                
                # Build command
                cmd = ['yt-dlp']
                
                # Add progress template for parsing
                cmd.extend(['--newline', '--progress'])
                
                # Quality/format selection
                format_option = self.options.get('format', 'best')
                if format_option == 'best':
                    if self.options.get('prefer_free_formats'):
                        cmd.extend(['-f', 'bv*+ba/b'])
                    else:
                        cmd.extend(['-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'])
                elif format_option == 'worst':
                    cmd.extend(['-f', 'worstvideo+worstaudio/worst'])
                elif format_option == 'bestaudio':
                    cmd.extend(['-f', 'bestaudio/best'])
                else:
                    # Specific quality like 1080p, 720p, etc.
                    quality = format_option.replace('p', '')
                    cmd.extend(['-f', f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]'])
                
                # Output format conversion
                output_format = self.options.get('output_format', 'default')
                if output_format != 'default':
                    if output_format in ['mp3', 'wav', 'flac', 'm4a', 'opus']:
                        # Audio formats
                        cmd.extend(['-x', '--audio-format', output_format])
                        if output_format == 'mp3':
                            cmd.extend(['--audio-quality', '0'])  # Best quality
                    else:
                        # Video format conversion
                        cmd.extend(['--remux-video', output_format])
                
                # Playlist handling
                if not self.options.get('download_playlist', True):
                    cmd.append('--no-playlist')
                
                # Output path and filename template
                output_path = self.options.get('output_path', os.path.expanduser("~/Downloads"))
                if self.options.get('download_playlist', True):
                    # Create playlist folder
                    output_template = os.path.join(output_path, '%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s')
                else:
                    output_template = os.path.join(output_path, '%(title)s.%(ext)s')
                cmd.extend(['-o', output_template])
                
                # Subtitles
                if self.options.get('subtitles'):
                    cmd.extend(['--write-sub', '--write-auto-sub', '--sub-lang', 'en,es,fr,de,ja'])
                    if self.options.get('embed_subs'):
                        cmd.append('--embed-subs')
                
                # Thumbnail
                if self.options.get('thumbnail'):
                    cmd.append('--write-thumbnail')
                    if self.options.get('embed_thumbnail'):
                        cmd.append('--embed-thumbnail')
                
                # Additional options
                if self.options.get('keep_video'):
                    cmd.append('-k')
                
                # Add URL
                cmd.append(url)
                
                # Create process
                self.process = QProcess()
                self.process.readyReadStandardOutput.connect(self.handle_output)
                self.process.readyReadStandardError.connect(self.handle_error)
                
                # Start process
                self.progress.emit(f"Command: {' '.join(cmd)}\n")
                self.process.start(cmd[0], cmd[1:])
                self.process.waitForFinished(-1)
                
                if self.is_cancelled:
                    self.progress.emit(f"⏹️ Stopped: {url}\n")
                elif self.process.exitCode() != 0:
                    self.error.emit(f"Download failed for {url} with exit code: {self.process.exitCode()}")
                else:
                    self.progress.emit(f"\n✅ Completed: {url}\n")
                
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")
        finally:
            if not self.is_cancelled:
                self.progress.emit("\n🎉 All downloads completed!")
            self.finished.emit()
    
    def handle_output(self):
        data = self.process.readAllStandardOutput().data().decode('utf-8')
        self.progress.emit(data)
        
        # Parse progress percentage
        for line in data.split('\n'):
            match = re.search(r'\[download\]\s+(\d+\.?\d*)%', line)
            if match:
                percent = int(float(match.group(1)))
                self.progress_percent.emit(percent)
    
    def handle_error(self):
        data = self.process.readAllStandardError().data().decode('utf-8')
        self.progress.emit(f"Error: {data}")
    
    def stop(self):
        self.is_cancelled = True
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(5000):
                self.process.kill()

class YTDLPGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.download_thread = None
        self.init_ui()
        self.check_dependencies()
        
    def init_ui(self):
        self.setWindowTitle('yt-dlp GUI')
        self.setGeometry(100, 100, 1000, 700)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Single download tab
        self.single_tab = QWidget()
        self.init_single_tab()
        self.tabs.addTab(self.single_tab, "Single Download")
        
        # Batch download tab
        self.batch_tab = QWidget()
        self.init_batch_tab()
        self.tabs.addTab(self.batch_tab, "Batch Download")
        
        # About tab
        self.about_tab = QWidget()
        self.init_about_tab()
        self.tabs.addTab(self.about_tab, "About")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Output section (shared between tabs)
        output_group = QGroupBox("Output Log")
        output_layout = QVBoxLayout()
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 9))
        self.output_text.setMaximumHeight(250)
        output_layout.addWidget(self.output_text)
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)
    
    def init_single_tab(self):
        layout = QVBoxLayout(self.single_tab)
        
        # URL input
        url_group = QGroupBox("Video/Playlist URL")
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube URL or playlist URL here...")
        url_layout.addWidget(self.url_input)
        url_group.setLayout(url_layout)
        layout.addWidget(url_group)
        
        # Options
        options_group = QGroupBox("Download Options")
        options_layout = QVBoxLayout()
        
        # First row - Format and Quality
        format_row = QHBoxLayout()
        
        # Video Quality
        format_row.addWidget(QLabel("Video Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "best",
            "2160p",
            "1440p",
            "1080p",
            "720p",
            "480p",
            "360p",
            "worst",
            "bestaudio"
        ])
        self.quality_combo.setMaximumWidth(150)
        format_row.addWidget(self.quality_combo)
        
        # Output format
        format_row.addWidget(QLabel("Convert to:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "default",
            "mp4",
            "webm",
            "mkv",
            "avi",
            "mp3",
            "wav",
            "flac",
            "m4a",
            "opus"
        ])
        self.format_combo.setMaximumWidth(150)
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        format_row.addWidget(self.format_combo)
        
        format_row.addStretch()
        options_layout.addLayout(format_row)
        
        # Second row - Checkboxes
        checkbox_row1 = QHBoxLayout()
        self.playlist_checkbox = QCheckBox("Download entire playlist")
        self.playlist_checkbox.setChecked(True)
        checkbox_row1.addWidget(self.playlist_checkbox)
        
        self.subtitles_checkbox = QCheckBox("Download subtitles")
        checkbox_row1.addWidget(self.subtitles_checkbox)
        
        self.embed_subs_checkbox = QCheckBox("Embed subtitles")
        self.embed_subs_checkbox.setEnabled(False)
        checkbox_row1.addWidget(self.embed_subs_checkbox)
        
        checkbox_row1.addStretch()
        options_layout.addLayout(checkbox_row1)
        
        # Third row - More checkboxes
        checkbox_row2 = QHBoxLayout()
        self.thumbnail_checkbox = QCheckBox("Download thumbnail")
        checkbox_row2.addWidget(self.thumbnail_checkbox)
        
        self.embed_thumb_checkbox = QCheckBox("Embed thumbnail")
        self.embed_thumb_checkbox.setEnabled(False)
        checkbox_row2.addWidget(self.embed_thumb_checkbox)
        
        self.keep_video_checkbox = QCheckBox("Keep original video (when converting)")
        checkbox_row2.addWidget(self.keep_video_checkbox)
        
        checkbox_row2.addStretch()
        options_layout.addLayout(checkbox_row2)
        
        # Connect checkbox signals
        self.subtitles_checkbox.stateChanged.connect(
            lambda state: self.embed_subs_checkbox.setEnabled(state == Qt.Checked)
        )
        self.thumbnail_checkbox.stateChanged.connect(
            lambda state: self.embed_thumb_checkbox.setEnabled(state == Qt.Checked)
        )
        
        # Output path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Save to:"))
        self.path_input = QLineEdit()
        self.path_input.setText(os.path.expanduser("~/Downloads"))
        path_layout.addWidget(self.path_input)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.browse_button)
        options_layout.addLayout(path_layout)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Control buttons
        self.init_control_buttons(layout)
        
        layout.addStretch()
    
    def init_batch_tab(self):
        layout = QVBoxLayout(self.batch_tab)
        
        # URL list
        url_group = QGroupBox("URL List (one per line)")
        url_layout = QVBoxLayout()
        
        self.batch_urls = QTextEdit()
        self.batch_urls.setPlaceholderText("Enter multiple URLs, one per line...\n\n"
                                          "Example:\n"
                                          "https://youtube.com/watch?v=...\n"
                                          "https://youtube.com/watch?v=...\n"
                                          "https://youtube.com/playlist?list=...")
        self.batch_urls.setMaximumHeight(150)
        url_layout.addWidget(self.batch_urls)
        
        # Batch controls
        batch_controls = QHBoxLayout()
        self.clear_button = QPushButton("Clear List")
        self.clear_button.clicked.connect(lambda: self.batch_urls.clear())
        self.load_file_button = QPushButton("Load from File")
        self.load_file_button.clicked.connect(self.load_urls_from_file)
        batch_controls.addWidget(self.clear_button)
        batch_controls.addWidget(self.load_file_button)
        batch_controls.addStretch()
        url_layout.addLayout(batch_controls)
        
        url_group.setLayout(url_layout)
        layout.addWidget(url_group)
        
        # Use same options as single tab (we'll reference them)
        layout.addWidget(QLabel("Options from Single Download tab will be used"))
        
        # Control buttons for batch
        self.init_control_buttons(layout, batch=True)
        
        layout.addStretch()
    
    def init_about_tab(self):
        layout = QVBoxLayout(self.about_tab)
        
        # Create about content
        about_content = QTextBrowser()
        about_content.setOpenExternalLinks(True)
        
        about_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                h1 {{ color: #2196F3; }}
                h2 {{ color: #666; }}
                .section {{ margin: 20px 0; }}
                .logo {{ text-align: center; margin: 20px 0; }}
                a {{ color: #2196F3; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                .license {{ background-color: #f5f5f5; padding: 10px; border-radius: 5px; font-family: monospace; }}
            </style>
        </head>
        <body>
            <div class="logo">
                <h1>🎬 yt-dlp GUI</h1>
                <h2>Version {__version__}</h2>
            </div>
            
            <div class="section">
                <h3>About</h3>
                <p>A feature-rich graphical interface for yt-dlp, making video downloading simple and efficient.</p>
            </div>
            
            <div class="section">
                <h3>Developer</h3>
                <p><strong>{__author__}</strong><br/>
                <a href="https://github.com/yourusername">GitHub Profile</a></p>
            </div>
            
            <div class="section">
                <h3>Features</h3>
                <ul>
                    <li>Single and batch download support</li>
                    <li>Quality selection (up to 4K)</li>
                    <li>Format conversion (video & audio)</li>
                    <li>Playlist download support</li>
                    <li>Subtitle and thumbnail embedding</li>
                    <li>Progress tracking</li>
                </ul>
            </div>
            
            <div class="section">
                <h3>Dependencies</h3>
                <ul>
                    <li><a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> - The core download engine</li>
                    <li><a href="https://ffmpeg.org/">ffmpeg</a> - For media conversion</li>
                    <li><a href="https://www.riverbankcomputing.com/software/pyqt/">PyQt5</a> - GUI framework</li>
                </ul>
            </div>
            
            <div class="section">
                <h3>License</h3>
                <div class="license">
                MIT License<br/><br/>
                Copyright (c) 2024 {__author__}<br/><br/>
                Permission is hereby granted, free of charge, to any person obtaining a copy<br/>
                of this software and associated documentation files (the "Software"), to deal<br/>
                in the Software without restriction, including without limitation the rights<br/>
                to use, copy, modify, merge, publish, distribute, sublicense, and/or sell<br/>
                copies of the Software, and to permit persons to whom the Software is<br/>
                furnished to do so, subject to the following conditions:<br/><br/>
                The above copyright notice and this permission notice shall be included in all<br/>
                copies or substantial portions of the Software.<br/><br/>
                THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR<br/>
                IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,<br/>
                FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
                </div>
            </div>
            
            <div class="section">
                <h3>Support</h3>
                <p>For issues, feature requests, or contributions, please visit:<br/>
                <a href="https://github.com/yourusername/yt-dlp-gui">Project Repository</a></p>
            </div>
        </body>
        </html>
        """
        
        about_content.setHtml(about_html)
        layout.addWidget(about_content)
    
    def init_control_buttons(self, layout, batch=False):
        button_layout = QHBoxLayout()
        
        if batch:
            self.batch_download_button = QPushButton("Start Batch Download")
            self.batch_download_button.clicked.connect(self.start_batch_download)
            self.batch_download_button.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            button_layout.addWidget(self.batch_download_button)
            
            self.batch_stop_button = QPushButton("Stop")
            self.batch_stop_button.clicked.connect(self.stop_download)
            self.batch_stop_button.setEnabled(False)
            self.batch_stop_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                }
            """)
            button_layout.addWidget(self.batch_stop_button)
        else:
            self.download_button = QPushButton("Download")
            self.download_button.clicked.connect(self.start_download)
            self.download_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            button_layout.addWidget(self.download_button)
            
            self.stop_button = QPushButton("Stop")
            self.stop_button.clicked.connect(self.stop_download)
            self.stop_button.setEnabled(False)
            self.stop_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                }
            """)
            button_layout.addWidget(self.stop_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
    
    def on_format_changed(self, format_text):
        # Disable quality selection for audio formats
        is_audio_format = format_text in ['mp3', 'wav', 'flac', 'm4a', 'opus']
        if is_audio_format:
            self.quality_combo.setCurrentText("bestaudio")
            self.quality_combo.setEnabled(False)
        else:
            self.quality_combo.setEnabled(True)
    
    def check_dependencies(self):
        """Check if yt-dlp and ffmpeg are installed"""
        self.output_text.append("Checking dependencies...\n")
        
        # Check yt-dlp
        try:
            result = subprocess.run(['yt-dlp', '--version'], 
                                  capture_output=True, text=True, check=True)
            self.output_text.append(f"✓ yt-dlp version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.output_text.append("✗ yt-dlp not found!")
            QMessageBox.warning(self, "yt-dlp not found", 
                              "yt-dlp is not installed. Please install it using:\n\n"
                              "pip install yt-dlp\n\n"
                              "or download from https://github.com/yt-dlp/yt-dlp")
        
        # Check ffmpeg
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         capture_output=True, check=True)
            self.output_text.append("✓ ffmpeg is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.output_text.append("✗ ffmpeg not found!")
            QMessageBox.warning(self, "ffmpeg not found", 
                              "ffmpeg is required for format conversion.\n\n"
                              "Please install ffmpeg:\n"
                              "• Windows: Download from https://ffmpeg.org\n"
                              "• Mac: brew install ffmpeg\n"
                              "• Linux: sudo apt install ffmpeg")
        
        self.output_text.append("\n" + "="*50 + "\n")
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.path_input.setText(folder)
    
    def load_urls_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load URL List", "", "Text Files (*.txt)")
        if file_path:
            with open(file_path, 'r') as f:
                self.batch_urls.setText(f.read())
    
    def get_download_options(self):
        """Get options from UI elements"""
        return {
            'format': self.quality_combo.currentText(),
            'output_format': self.format_combo.currentText(),
            'output_path': self.path_input.text(),
            'download_playlist': self.playlist_checkbox.isChecked(),
            'subtitles': self.subtitles_checkbox.isChecked(),
            'embed_subs': self.embed_subs_checkbox.isChecked(),
            'thumbnail': self.thumbnail_checkbox.isChecked(),
            'embed_thumbnail': self.embed_thumb_checkbox.isChecked(),
            'keep_video': self.keep_video_checkbox.isChecked(),
        }
    
    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "No URL", "Please enter a URL")
            return
        
        self.run_download([url])
    
    def start_batch_download(self):
        urls = [url.strip() for url in self.batch_urls.toPlainText().split('\n') 
                if url.strip()]
        if not urls:
            QMessageBox.warning(self, "No URLs", "Please enter at least one URL")
            return
        
        self.run_download(urls)
    
    def run_download(self, urls):
        # Clear output and show progress bar
        self.output_text.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Disable download buttons, enable stop buttons
        self.download_button.setEnabled(False)
        self.batch_download_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.batch_stop_button.setEnabled(True)
        
        # Get options and create thread
        options = self.get_download_options()
        self.download_thread = DownloadThread(urls, options)
        self.download_thread.progress.connect(self.update_output)
        self.download_thread.progress_percent.connect(self.update_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.error.connect(self.download_error)
        self.download_thread.start()
    
    def stop_download(self):
        if self.download_thread and self.download_thread.isRunning():
            reply = QMessageBox.question(self, 'Stop Download',
                                       'Are you sure you want to stop the current download?',
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.output_text.append("\n⚠️ Stopping download...")
                self.download_thread.stop()
    
    def update_output(self, text):
        self.output_text.insertPlainText(text)
        # Auto-scroll to bottom
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.output_text.setTextCursor(cursor)
    
    def update_progress(self, percent):
        self.progress_bar.setValue(percent)
    
    def download_finished(self):
        self.download_button.setEnabled(True)
        self.batch_download_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.batch_stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
    
    def download_error(self, error_msg):
        self.output_text.append(f"\n❌ Error: {error_msg}")
    
    def closeEvent(self, event):
        if self.download_thread and self.download_thread.isRunning():
            reply = QMessageBox.question(self, 'Close Application',
                                       'A download is in progress. Are you sure you want to exit?',
                                       QMessageBox.Yes | QMessageBox.No,
                                       QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.download_thread.stop()
                self.download_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    window = YTDLPGui()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

