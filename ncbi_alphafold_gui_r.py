import sys
import os
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QRadioButton, QGroupBox, 
                             QTextEdit, QSpinBox, QMessageBox, QProgressBar, QButtonGroup,
                             QSplitter, QFileDialog, QTabWidget, QCheckBox, QComboBox,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QScrollArea, QTabWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ncbi_threads import NCBISearchThread, SequenceDownloadThread
from ncbi_bulk_threads import BulkDownloadThread, ExcelLoadThread, RetryFailedThread
from preprocess_dna import SequenceProcessor
from alphafold_crawler_2 import AlphaFoldSubmitter
import pandas as pd
from pathlib import Path
from ncbi_bulk_threads import BulkPreprocessingThread

from protein_roi_loader import (
    ProteinDataLoader, ROIDataLoader, JobPairGenerator, 
    DataValidator, load_and_validate_protein_data, 
    load_and_validate_roi_data, create_job_batch
)
from alphafold_batch_handler import AlphaFoldBatchHandler
from datetime import datetime
from alphafold_login import AlphaFoldLogin

import re  # Add this if not already imported
from datetime import datetime  # Add this if not already imported

# Add these new imports for the AlphaFold automation
from alphafold_job_handler import AlphaFoldJobHandler
from alphafold_browser_manager import AlphaFoldBrowserManager
from alphafold_job_submitter import AlphaFoldJobSubmitter
from alphafold_job_monitor import AlphaFoldJobMonitor
from alphafold_job_downloader import AlphaFoldJobDownloader

# Configuration constants you can adjust
class BatchConfig:
    # Job timing (in seconds)
    JOB_SUBMISSION_DELAY = 30  # Delay between job submissions
    STATUS_CHECK_INTERVAL = 60  # How often to check job status
    
    # Job limits
    DEFAULT_DAILY_LIMIT = 30  # Default daily job limit
    MAX_DAILY_LIMIT = 100     # Maximum daily job limit
    
    # Sequence validation
    MIN_PROTEIN_LENGTH = 10   # Minimum protein sequence length
    MAX_PROTEIN_LENGTH = 2000 # Maximum recommended protein length
    MIN_DNA_LENGTH = 10       # Minimum DNA sequence length
    MAX_DNA_LENGTH = 500      # Maximum recommended DNA length
    
    # File paths
    RESULTS_BASE_DIR = "alphafold_batch_results"
    LOG_DIR = "batch_logs"
    TEMP_DIR = "temp_files"
    
    # AlphaFold settings
    USE_MULTIMER_MODEL = False  # Whether to use multimer model by default
    SAVE_ALL_MODELS = True      # Whether to save all 5 models

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NCBI Sequence Retriever & AlphaFold Submitter")
        self.setMinimumSize(1400, 800)

        self.preprocessing_thread = None
        self.preprocessing_results_df = None
        self.fasta_directory_path = None

        self.fasta_dir_label = None
        self.bulk_roi_input = None
        self.excel_output_label = None
        self.process_directory_button = None
        self.preprocessing_progress = None
        self.preprocessing_status = None
        self.files_processed_label = None
        self.roi_found_label = None
        self.results_table = None
        self.export_results_button = None

        # AlphaFold 3 Bulk Uploading
        self.protein_data = []
        self.selected_protein = None
        self.roi_data = []
        self.batch_jobs = []
        self.current_job_index = 0
        self.batch_handler = None 
        
        # Store search results
        self.search_results = []
        self.selected_result_id = None
        self.current_fasta_path = None
        self.roi_sequence = None
        self.protein_sequence_text = None

        # AlphaFold login variables
        self.alphafold_login_handler = None
        self.is_logged_in = False
        
        # Bulk download variables
        self.current_gene_list = []
        self.bulk_download_thread = None
        self.excel_load_thread = None
        self.retry_thread = None
        
        # Create the AlphaFold submitter
        self.alphafold_submitter = AlphaFoldSubmitter()
        # Download configuration variables
        self.download_directory = None

        # Batch processing tracking
        self.successful_jobs = []
        self.failed_jobs = []

        # AlphaFold automation handler
        self.batch_handler = None
        
        self.initUI()
        
    def initUI(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Create a splitter to divide the window
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left side - NCBI Sequence Retriever (with tabs for single and bulk)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # NCBI Retriever title
        ncbi_title = QLabel("NCBI Sequence Retriever")
        ncbi_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        left_layout.addWidget(ncbi_title)
        
        # Create tabs for single and bulk download (LEFT SIDE TABS)
        ncbi_tabs = QTabWidget()
        left_layout.addWidget(ncbi_tabs)
        
        # Tab 1: Single Sequence Download
        single_tab = self.create_single_download_tab()
        ncbi_tabs.addTab(single_tab, "Single Download")
        
        # Tab 2: Bulk Sequence Download
        bulk_tab = self.create_bulk_download_tab()
        ncbi_tabs.addTab(bulk_tab, "Bulk Download")
        
        # Right side - AlphaFold Predictor (this creates its own internal tabs)
        right_widget = self.create_alphafold_tab()
        
        # Add widgets to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # Set initial sizes (60/40 split to accommodate bulk download table)
        splitter.setSizes([840, 560])
    
    def create_single_download_tab(self):
        """Create the single sequence download tab"""
        single_widget = QWidget()
        single_layout = QVBoxLayout(single_widget)
        
        # Input section
        input_group = QGroupBox("Search Parameters")
        input_layout = QVBoxLayout()
        
        # Gene name input
        gene_layout = QHBoxLayout()
        gene_label = QLabel("Gene/Protein Name:")
        self.gene_input = QLineEdit()
        gene_layout.addWidget(gene_label)
        gene_layout.addWidget(self.gene_input)
        input_layout.addLayout(gene_layout)
        
        # Organism input
        org_layout = QHBoxLayout()
        org_label = QLabel("Organism:")
        self.org_input = QLineEdit()
        self.org_input.setText("homo sapiens")  # Default value
        org_layout.addWidget(org_label)
        org_layout.addWidget(self.org_input)
        input_layout.addLayout(org_layout)
        
        # Sequence length input
        length_layout = QHBoxLayout()
        length_label = QLabel("Sequence Length:")
        self.length_input = QSpinBox()
        self.length_input.setRange(0, 1000000)  # 0 means full sequence
        self.length_input.setValue(2100)  # Default value
        self.length_input.setSpecialValueText("Full Length")  # Display "Full Length" when value is 0
        length_layout.addWidget(length_label)
        length_layout.addWidget(self.length_input)
        length_layout.addWidget(QLabel("bases (0 = full length)"))
        length_layout.addStretch()
        input_layout.addLayout(length_layout)
        
        # Email input
        email_layout = QHBoxLayout()
        email_label = QLabel("Your Email:")
        self.email_input = QLineEdit()
        email_layout.addWidget(email_label)
        email_layout.addWidget(self.email_input)
        input_layout.addLayout(email_layout)
        
        # Search button
        self.search_button = QPushButton("Search Sequences")
        self.search_button.clicked.connect(self.search_ncbi)
        input_layout.addWidget(self.search_button)
        
        input_group.setLayout(input_layout)
        single_layout.addWidget(input_group)
        
        # Results display
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()
        
        # Results text area
        self.results_display = QTextEdit()
        self.results_display.setReadOnly(True)
        results_layout.addWidget(self.results_display)
        
        # Selection area (will be populated when results are available)
        self.selection_group = QGroupBox("Select a Sequence")
        self.selection_layout = QVBoxLayout()
        self.selection_group.setLayout(self.selection_layout)
        self.selection_group.setVisible(False)
        results_layout.addWidget(self.selection_group)
        
        results_group.setLayout(results_layout)
        single_layout.addWidget(results_group)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.download_button = QPushButton("Download Selected")
        self.download_button.clicked.connect(self.download_sequence)
        self.download_button.setEnabled(False)
        action_layout.addWidget(self.download_button)
        
        self.send_to_alphafold_button = QPushButton("Send to AlphaFold →")
        self.send_to_alphafold_button.clicked.connect(self.send_to_alphafold)
        self.send_to_alphafold_button.setEnabled(False)
        action_layout.addWidget(self.send_to_alphafold_button)
        
        single_layout.addLayout(action_layout)
        
        # Status bar and progress
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        
        single_layout.addLayout(status_layout)
        
        return single_widget
    
    def create_bulk_download_tab(self):
        """Create the bulk sequence download tab"""
        bulk_widget = QWidget()
        bulk_layout = QVBoxLayout(bulk_widget)
        
        # File loading section
        file_group = QGroupBox("Load Gene List from Excel")
        file_layout = QVBoxLayout()
        
        # File selection
        file_select_layout = QHBoxLayout()
        self.excel_path_label = QLabel("No file selected")
        self.browse_excel_button = QPushButton("Browse Excel File")
        self.browse_excel_button.clicked.connect(self.browse_excel_file)
        file_select_layout.addWidget(QLabel("Excel File:"))
        file_select_layout.addWidget(self.excel_path_label)
        file_select_layout.addWidget(self.browse_excel_button)
        file_layout.addLayout(file_select_layout)
        
        # Column configuration
        col_config_layout = QHBoxLayout()
        
        # Gene column
        col_config_layout.addWidget(QLabel("Gene Column:"))
        self.gene_column_combo = QComboBox()
        self.gene_column_combo.addItems(["Column A (0)", "Column B (1)", "Column C (2)", "Column D (3)"])
        col_config_layout.addWidget(self.gene_column_combo)
        
        # Organism column (optional)
        col_config_layout.addWidget(QLabel("Organism Column:"))
        self.organism_column_combo = QComboBox()
        self.organism_column_combo.addItems(["None", "Column A (0)", "Column B (1)", "Column C (2)", "Column D (3)"])
        col_config_layout.addWidget(self.organism_column_combo)
        
        # Status column (optional)
        col_config_layout.addWidget(QLabel("Status Column:"))
        self.status_column_combo = QComboBox()
        self.status_column_combo.addItems(["None", "Column A (0)", "Column B (1)", "Column C (2)", "Column D (3)"])
        self.status_column_combo.setCurrentText("Column B (1)")
        col_config_layout.addWidget(self.status_column_combo)
        
        file_layout.addLayout(col_config_layout)
        
        # Load button
        self.load_excel_button = QPushButton("Load Gene List")
        self.load_excel_button.clicked.connect(self.load_excel_file)
        self.load_excel_button.setEnabled(False)
        file_layout.addWidget(self.load_excel_button)
        
        file_group.setLayout(file_layout)
        bulk_layout.addWidget(file_group)
        
        # Gene list display
        list_group = QGroupBox("Gene List")
        list_layout = QVBoxLayout()
        
        # Info labels
        info_layout = QHBoxLayout()
        self.gene_count_label = QLabel("Genes loaded: 0")
        self.organism_info_label = QLabel("Default organism: homo sapiens")
        info_layout.addWidget(self.gene_count_label)
        info_layout.addWidget(self.organism_info_label)
        info_layout.addStretch()
        list_layout.addLayout(info_layout)
        
        # Gene table
        self.gene_table = QTableWidget()
        self.gene_table.setColumnCount(4)
        self.gene_table.setHorizontalHeaderLabels(["Gene Name", "Organism", "Status", "Row"])
        self.gene_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.gene_table.setMaximumHeight(200)
        list_layout.addWidget(self.gene_table)
        
        list_group.setLayout(list_layout)
        bulk_layout.addWidget(list_group)
        
        # Bulk download settings
        settings_group = QGroupBox("Bulk Download Settings")
        settings_layout = QVBoxLayout()
        
        # Settings row 1
        settings_row1 = QHBoxLayout()
        
        # Email
        settings_row1.addWidget(QLabel("Email:"))
        self.bulk_email_input = QLineEdit()
        settings_row1.addWidget(self.bulk_email_input)

        # IMPORTANT FIX: Connect email input to update button state
        self.bulk_email_input.textChanged.connect(self.update_bulk_download_button_state)
        
        # Sequence length
        settings_row1.addWidget(QLabel("Sequence Length:"))
        self.bulk_length_input = QSpinBox()
        self.bulk_length_input.setRange(0, 1000000)
        self.bulk_length_input.setValue(2100)
        self.bulk_length_input.setSpecialValueText("Full Length")
        settings_row1.addWidget(self.bulk_length_input)
        
        settings_layout.addLayout(settings_row1)
        
        # Settings row 2
        settings_row2 = QHBoxLayout()
        
        # Output directory
        settings_row2.addWidget(QLabel("Output Directory:"))
        self.output_dir_label = QLabel("bulk_sequences")
        self.browse_output_button = QPushButton("Browse")
        self.browse_output_button.clicked.connect(self.browse_output_directory)
        settings_row2.addWidget(self.output_dir_label)
        settings_row2.addWidget(self.browse_output_button)
        
        # Delay between requests
        settings_row2.addWidget(QLabel("Delay (sec):"))
        self.delay_input = QSpinBox()
        self.delay_input.setRange(1, 60)
        self.delay_input.setValue(2)
        settings_row2.addWidget(self.delay_input)
        
        settings_layout.addLayout(settings_row2)
        
        settings_group.setLayout(settings_layout)
        bulk_layout.addWidget(settings_group)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.start_bulk_button = QPushButton("Start Bulk Download")
        self.start_bulk_button.clicked.connect(self.start_bulk_download)
        self.start_bulk_button.setEnabled(False)
        control_layout.addWidget(self.start_bulk_button)
        
        self.stop_bulk_button = QPushButton("Stop Download")
        self.stop_bulk_button.clicked.connect(self.stop_bulk_download)
        self.stop_bulk_button.setEnabled(False)
        control_layout.addWidget(self.stop_bulk_button)
        
        self.retry_failed_button = QPushButton("Retry Failed")
        self.retry_failed_button.clicked.connect(self.retry_failed_downloads)
        self.retry_failed_button.setEnabled(False)
        control_layout.addWidget(self.retry_failed_button)
        
        bulk_layout.addLayout(control_layout)
        
        # Progress section
        progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout()
        
        # Progress bar
        self.bulk_progress_bar = QProgressBar()
        progress_layout.addWidget(self.bulk_progress_bar)
        
        # Status labels
        status_info_layout = QHBoxLayout()
        self.bulk_status_label = QLabel("Ready for bulk download")
        self.bulk_stats_label = QLabel("Downloaded: 0 | Failed: 0")
        status_info_layout.addWidget(self.bulk_status_label)
        status_info_layout.addWidget(self.bulk_stats_label)
        progress_layout.addLayout(status_info_layout)
        
        # Log area
        self.bulk_log = QTextEdit()
        self.bulk_log.setReadOnly(True)
        self.bulk_log.setMaximumHeight(150)
        progress_layout.addWidget(self.bulk_log)
        
        progress_group.setLayout(progress_layout)
        bulk_layout.addWidget(progress_group)
        
        return bulk_widget
    
    def update_bulk_download_button_state(self):
        """Update the state of the bulk download button"""
        has_genes = len(self.current_gene_list) > 0
        has_email = self.bulk_email_input.text().strip() != "" and '@' in self.bulk_email_input.text().strip()
    
        # Enable button only if we have both genes and a valid email
        self.start_bulk_button.setEnabled(has_genes and has_email)
    
        # Debug print to help troubleshoot
        print(f"Button state update: has_genes={has_genes}, has_email={has_email}, button_enabled={has_genes and has_email}")

    # Single NCBI search remains unchanged
    def search_ncbi(self):
        """Perform a search on NCBI"""
        # Get input values
        gene = self.gene_input.text().strip()
        organism = self.org_input.text().strip()
        email = self.email_input.text().strip()
        
        # Basic validation
        if not gene:
            QMessageBox.warning(self, "Input Error", "Please enter a gene or protein name.")
            return
        
        if not email or '@' not in email:
            QMessageBox.warning(self, "Input Error", "Please enter a valid email address.")
            return
        
        # Clear previous results
        self.results_display.clear()
        self.clear_selection_widgets()
        self.search_results = []
        self.selected_result_id = None
        self.download_button.setEnabled(False)
        self.send_to_alphafold_button.setEnabled(False)
        
        # Update status
        self.status_label.setText(f"Searching for '{gene}' in '{organism}'...")
        self.progress_bar.setVisible(True)
        
        # Create and start the search thread
        self.search_thread = NCBISearchThread(gene, organism, email)
        self.search_thread.result_signal.connect(self.display_search_results)
        self.search_thread.error_signal.connect(self.handle_error)
        self.search_thread.start()

    def display_search_results(self, results):
        """Display search results and create selection widgets"""
        self.search_results = results
        
        # Display the results in the text area
        self.results_display.append(f"Found {len(results)} sequences:")
        for i, result in enumerate(results, 1):
            mane_tag = " (MANE Select)" if result["is_mane"] else ""
            refseq_tag = " (RefSeq)" if result["is_refseq"] and not result["is_mane"] else ""
            self.results_display.append(f"{i}. {result['accession']}{mane_tag}{refseq_tag}")
            self.results_display.append(f"   {result['title']}")
            self.results_display.append(f"   Length: {result['length']} bp")
            self.results_display.append("")
        
        # Create radio buttons for selection
        self.clear_selection_widgets()
        self.selection_group.setVisible(True)
        
        self.radio_group = QButtonGroup(self)
        
        for i, result in enumerate(results):
            radio = QRadioButton(f"{result['accession']} - {result['title'][:50]}...")
            
            # Add tags for special types
            if result["is_mane"]:
                radio.setText(radio.text() + " (MANE Select)")
                radio.setChecked(True)  # Auto-select MANE Select
                self.selected_result_id = result["id"]
            elif result["is_refseq"]:
                radio.setText(radio.text() + " (RefSeq)")
            
            radio.setProperty("result_id", result["id"])
            radio.toggled.connect(self.on_selection_changed)
            self.selection_layout.addWidget(radio)
            self.radio_group.addButton(radio)
        
        # If no MANE Select or RefSeq selected, select the first one
        if self.selected_result_id is None and results:
            first_radio = self.radio_group.buttons()[0]
            first_radio.setChecked(True)
            self.selected_result_id = results[0]["id"]
        
        # Update status
        self.status_label.setText(f"Found {len(results)} sequences. Select one to download.")
        self.progress_bar.setVisible(False)
        self.download_button.setEnabled(True)
    
    def on_selection_changed(self):
        """Handle selection of a sequence"""
        sender = self.sender()
        if sender.isChecked():
            self.selected_result_id = sender.property("result_id")
            self.download_button.setEnabled(True)
    
    def clear_selection_widgets(self):
        """Clear the selection radio buttons"""
        # Remove all widgets from selection layout
        while self.selection_layout.count():
            item = self.selection_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def download_sequence(self):
        """Download the selected sequence"""
        if not self.selected_result_id:
            QMessageBox.warning(self, "Selection Error", "Please select a sequence to download.")
            return
        
        email = self.email_input.text().strip()
        seq_length = self.length_input.value()
        
        # Create output directory in the current working directory if it doesn't exist
        output_dir = "downloaded_sequences"
        os.makedirs(output_dir, exist_ok=True)
        
        # Update status
        self.status_label.setText("Downloading sequence...")
        self.progress_bar.setVisible(True)
        self.download_button.setEnabled(False)  # Disable button during download
        
        # Create and start the download thread
        self.download_thread = SequenceDownloadThread(self.selected_result_id, seq_length, email, output_dir)
        self.download_thread.finished_signal.connect(self.handle_download_finished)
        self.download_thread.error_signal.connect(self.handle_error)
        
        # Connect to the new progress signal
        self.download_thread.progress_signal.connect(self.update_status)
        
        self.download_thread.start()
    
    def update_status(self, message):
        """Update the status label with progress messages"""
        self.status_label.setText(message)
        # Also log to the results display for a record
        self.results_display.append(f"[Status] {message}")

    def handle_download_finished(self, filepath):
        """Handle completion of the download"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Sequence downloaded to {filepath}")
        self.download_button.setEnabled(True)  # Re-enable the button
        self.send_to_alphafold_button.setEnabled(True)  # Enable send to AlphaFold button
        
        # Store the filepath for later use
        self.current_fasta_path = filepath
        
        # Read a bit of the file to confirm content
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_preview = f.read(200)  # Read first 200 chars
            
            # Show success message with file preview
            QMessageBox.information(self, "Download Complete", 
                                  f"The sequence has been downloaded successfully to:\n{filepath}\n\n"
                                  f"Preview of file content:\n{file_preview}")
        except Exception as e:
            QMessageBox.warning(self, "Download Issue", 
                              f"File was created but there may be issues with it: {str(e)}")
    
    def handle_error(self, error_message):
        """Handle errors from worker threads"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error occurred")
        self.download_button.setEnabled(True)  # Re-enable the button
        
        # Show error dialog with details
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setText("An error occurred during the operation")
        error_dialog.setInformativeText(error_message)
        error_dialog.setWindowTitle("Error")
        error_dialog.setDetailedText(error_message)
        error_dialog.exec()
        
        # Also log the error to the results display
        self.results_display.append(f"[ERROR] {error_message}")
    
    def send_to_alphafold(self):
        """Send the downloaded sequence to the AlphaFold tab"""
        if not self.current_fasta_path:
            QMessageBox.warning(self, "Error", "No sequence has been downloaded yet.")
            return
        
        # Update the file path label
        self.file_path_label.setText(self.current_fasta_path)
        
        # Enable the find ROI button
        self.find_roi_button.setEnabled(True)
        
        # Optionally automatically find the ROI
        self.find_roi()
    
    # Additional helper method for the protein management tab
    def create_protein_management_tab(self):
        """Create the protein sequence management tab (Updated version)"""
        protein_widget = QWidget()
        protein_layout = QVBoxLayout(protein_widget)
        
        # Protein Excel Loading Section
        excel_group = QGroupBox("Load Protein Sequences from Excel")
        excel_layout = QVBoxLayout()
        
        # File selection
        file_select_layout = QHBoxLayout()
        self.protein_excel_label = QLabel("No file selected")
        self.browse_protein_excel_button = QPushButton("Browse Excel File")
        self.browse_protein_excel_button.clicked.connect(self.browse_protein_excel_file)
        file_select_layout.addWidget(QLabel("Protein Excel File:"))
        file_select_layout.addWidget(self.protein_excel_label)
        file_select_layout.addWidget(self.browse_protein_excel_button)
        excel_layout.addLayout(file_select_layout)
        
        # Column configuration
        col_config_layout = QHBoxLayout()
        col_config_layout.addWidget(QLabel("Protein Name Column:"))
        self.protein_name_column_combo = QComboBox()
        self.protein_name_column_combo.addItems(["Column A (0)", "Column B (1)", "Column C (2)", "Column D (3)"])
        col_config_layout.addWidget(self.protein_name_column_combo)
        
        col_config_layout.addWidget(QLabel("Protein Sequence Column:"))
        self.protein_seq_column_combo = QComboBox()
        self.protein_seq_column_combo.addItems(["Column A (0)", "Column B (1)", "Column C (2)", "Column D (3)"])
        self.protein_seq_column_combo.setCurrentText("Column B (1)")
        col_config_layout.addWidget(self.protein_seq_column_combo)
        
        excel_layout.addLayout(col_config_layout)
        
        # Load button
        self.load_protein_excel_button = QPushButton("Load Protein Sequences")
        self.load_protein_excel_button.clicked.connect(self.load_protein_excel_file)
        self.load_protein_excel_button.setEnabled(False)
        excel_layout.addWidget(self.load_protein_excel_button)
        
        excel_group.setLayout(excel_layout)
        protein_layout.addWidget(excel_group)
        
        # Protein Selection Section
        selection_group = QGroupBox("Select Protein for AlphaFold Prediction")
        selection_layout = QVBoxLayout()
        
        # Info and export buttons
        info_layout = QHBoxLayout()
        self.protein_count_label = QLabel("Proteins loaded: 0")
        info_layout.addWidget(self.protein_count_label)
        info_layout.addStretch()
        
        self.export_proteins_button = QPushButton("Export Protein Summary")
        self.export_proteins_button.clicked.connect(self.export_protein_summary)
        self.export_proteins_button.setEnabled(False)
        info_layout.addWidget(self.export_proteins_button)
        
        selection_layout.addLayout(info_layout)
        
        # Radio button container
        self.protein_radio_container = QWidget()
        self.protein_radio_layout = QVBoxLayout(self.protein_radio_container)
        self.protein_radio_group = QButtonGroup(self)
        
        # Scroll area for protein selection
        protein_scroll = QScrollArea()
        protein_scroll.setWidget(self.protein_radio_container)
        protein_scroll.setWidgetResizable(True)
        protein_scroll.setMaximumHeight(250)
        selection_layout.addWidget(protein_scroll)
        
        selection_group.setLayout(selection_layout)
        protein_layout.addWidget(selection_group)
        
        # Selected Protein Preview
        preview_group = QGroupBox("Selected Protein Details")
        preview_layout = QVBoxLayout()
        
        # Protein info display
        info_layout = QHBoxLayout()
        self.selected_protein_name_label = QLabel("Name: None selected")
        self.selected_protein_length_label = QLabel("Length: 0 AA")
        info_layout.addWidget(self.selected_protein_name_label)
        info_layout.addWidget(self.selected_protein_length_label)
        info_layout.addStretch()
        preview_layout.addLayout(info_layout)
        
        # Protein sequence preview
        preview_layout.addWidget(QLabel("Sequence Preview:"))
        self.protein_sequence_preview = QTextEdit()
        self.protein_sequence_preview.setReadOnly(True)
        self.protein_sequence_preview.setMaximumHeight(120)
        preview_layout.addWidget(self.protein_sequence_preview)
        
        preview_group.setLayout(preview_layout)
        protein_layout.addWidget(preview_group)
        
        # Initialize variables
        self.protein_data = []
        self.selected_protein = None
        
        return protein_widget

    def create_alphafold_tab(self):
        """Create the AlphaFold tab with updated preprocessing functionality"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # AlphaFold Predictor title
        af_title = QLabel("AlphaFold 3 Predictor")
        af_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        right_layout.addWidget(af_title)
        
        # Create tabs for the right side
        tab_widget = QTabWidget()
        right_layout.addWidget(tab_widget)
        
        # Tab 1: Sequence Pre-processor (existing functionality with sub-tabs)
        preprocessor_tab = QWidget()
        preprocessor_layout = QVBoxLayout(preprocessor_tab)
        
        # Create a tab widget for single vs bulk preprocessing
        preprocess_tabs = QTabWidget()
        preprocessor_layout.addWidget(preprocess_tabs)
        
        # Single File Processing Tab
        single_process_tab = QWidget()
        single_layout = QVBoxLayout(single_process_tab)
        
        # File loading section
        file_group = QGroupBox("Load FASTA Sequence")
        file_layout = QVBoxLayout()
        
        file_buttons_layout = QHBoxLayout()
        self.load_file_button = QPushButton("Load FASTA File")
        self.load_file_button.clicked.connect(self.load_fasta_file)
        file_buttons_layout.addWidget(self.load_file_button)
        
        self.paste_sequence_button = QPushButton("Paste Sequence")
        self.paste_sequence_button.clicked.connect(self.paste_sequence)
        file_buttons_layout.addWidget(self.paste_sequence_button)
        file_layout.addLayout(file_buttons_layout)
        
        # Display loaded file path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Current File:"))
        self.file_path_label = QLabel("No file loaded")
        path_layout.addWidget(self.file_path_label)
        path_layout.addStretch()
        file_layout.addLayout(path_layout)
        
        file_group.setLayout(file_layout)
        single_layout.addWidget(file_group)
        
        # ROI finder section
        roi_group = QGroupBox("Region of Interest (ROI) Finder")
        roi_layout = QVBoxLayout()
        
        roi_input_layout = QHBoxLayout()
        roi_input_layout.addWidget(QLabel("ROI Pattern:"))
        self.roi_input = QLineEdit("CACCTG")
        roi_input_layout.addWidget(self.roi_input)
        self.find_roi_button = QPushButton("Find ROI")
        self.find_roi_button.clicked.connect(self.find_roi)
        self.find_roi_button.setEnabled(False)
        roi_input_layout.addWidget(self.find_roi_button)
        roi_layout.addLayout(roi_input_layout)
        
        roi_layout.addWidget(QLabel("Found ROI Sub-Sequence:"))
        self.roi_result = QTextEdit()
        self.roi_result.setReadOnly(True)
        self.roi_result.setMaximumHeight(100)
        roi_layout.addWidget(self.roi_result)
        
        roi_group.setLayout(roi_layout)
        single_layout.addWidget(roi_group)
        
        preprocess_tabs.addTab(single_process_tab, "Single File")
        
        # Bulk Processing Tab
        bulk_process_tab = QWidget()
        bulk_layout = QVBoxLayout(bulk_process_tab)
        
        # Directory selection
        dir_group = QGroupBox("Select FASTA Directory")
        dir_layout = QVBoxLayout()
        
        dir_select_layout = QHBoxLayout()
        self.fasta_dir_label = QLabel("No directory selected")
        self.browse_fasta_dir_button = QPushButton("Browse Directory")
        self.browse_fasta_dir_button.clicked.connect(self.browse_fasta_directory)
        dir_select_layout.addWidget(QLabel("FASTA Directory:"))
        dir_select_layout.addWidget(self.fasta_dir_label)
        dir_select_layout.addWidget(self.browse_fasta_dir_button)
        dir_layout.addLayout(dir_select_layout)
        
        # ROI pattern for bulk processing
        bulk_roi_layout = QHBoxLayout()
        bulk_roi_layout.addWidget(QLabel("ROI Pattern:"))
        self.bulk_roi_input = QLineEdit("CACCTG")
        bulk_roi_layout.addWidget(self.bulk_roi_input)
        bulk_roi_layout.addStretch()
        dir_layout.addLayout(bulk_roi_layout)
        
        # Output file selection
        output_layout = QHBoxLayout()
        self.excel_output_label = QLabel("roi_analysis_summary.xlsx")
        self.browse_excel_output_button = QPushButton("Browse Output")
        self.browse_excel_output_button.clicked.connect(self.browse_excel_output)
        output_layout.addWidget(QLabel("Output Excel:"))
        output_layout.addWidget(self.excel_output_label)
        output_layout.addWidget(self.browse_excel_output_button)
        dir_layout.addLayout(output_layout)
        
        dir_group.setLayout(dir_layout)
        bulk_layout.addWidget(dir_group)
        
        # Processing controls
        control_group = QGroupBox("Processing Controls")
        control_layout = QVBoxLayout()
        
        self.process_directory_button = QPushButton("Process All FASTA Files")
        self.process_directory_button.clicked.connect(self.process_fasta_directory)
        self.process_directory_button.setEnabled(False)
        self.process_directory_button.setMinimumHeight(40)
        control_layout.addWidget(self.process_directory_button)
        
        self.preprocessing_progress = QProgressBar()
        control_layout.addWidget(self.preprocessing_progress)
        
        self.preprocessing_status = QLabel("Ready to process FASTA files")
        control_layout.addWidget(self.preprocessing_status)
        
        control_group.setLayout(control_layout)
        bulk_layout.addWidget(control_group)
        
        # Results display
        results_group = QGroupBox("Processing Results")
        results_layout = QVBoxLayout()
        
        summary_layout = QHBoxLayout()
        self.files_processed_label = QLabel("Files processed: 0")
        self.roi_found_label = QLabel("ROI sequences found: 0")
        summary_layout.addWidget(self.files_processed_label)
        summary_layout.addWidget(self.roi_found_label)
        summary_layout.addStretch()
        results_layout.addLayout(summary_layout)
        
        results_layout.addWidget(QLabel("Summary Preview (first 10 rows):"))
        self.results_table = QTableWidget()
        self.results_table.setMaximumHeight(200)
        results_layout.addWidget(self.results_table)
        
        self.export_results_button = QPushButton("Export Full Results to Excel")
        self.export_results_button.clicked.connect(self.export_preprocessing_results)
        self.export_results_button.setEnabled(False)
        results_layout.addWidget(self.export_results_button)
        
        results_group.setLayout(results_layout)
        bulk_layout.addWidget(results_group)
        
        preprocess_tabs.addTab(bulk_process_tab, "Bulk Processing")
        
        # Add protein sequence section to preprocessing tab
        protein_group = QGroupBox("Protein Sequence")
        protein_layout = QVBoxLayout()
        
        protein_layout.addWidget(QLabel("Enter Protein Sequence:"))
        self.protein_sequence = QTextEdit()
        self.protein_sequence.textChanged.connect(self.on_protein_sequence_changed)
        protein_layout.addWidget(self.protein_sequence)
        
        protein_group.setLayout(protein_layout)
        preprocessor_layout.addWidget(protein_group)
        
        # Add the preprocessor tab
        tab_widget.addTab(preprocessor_tab, "Sequence Pre-processor")
        
        # Tab 2: Protein Sequences (NEW - this was missing!)
        protein_tab = self.create_protein_management_tab()
        tab_widget.addTab(protein_tab, "Protein Sequences")
        
        # Tab 3: AlphaFold Submission (UPDATED)
        submission_tab = self.create_submission_tab()
        tab_widget.addTab(submission_tab, "AlphaFold Submission")
        
        # Tab 4: Results Viewer
        results_tab = QWidget()
        results_layout = QVBoxLayout(results_tab)
        
        results_layout.addWidget(QLabel("Your AlphaFold 3 Results:"))
        self.results_viewer = QTextEdit()
        self.results_viewer.setReadOnly(True)
        results_layout.addWidget(self.results_viewer)
        
        results_buttons_layout = QHBoxLayout()
        self.refresh_results_button = QPushButton("Refresh Results")
        self.refresh_results_button.clicked.connect(self.refresh_results)
        results_buttons_layout.addWidget(self.refresh_results_button)
        
        self.download_results_button = QPushButton("Download Results")
        self.download_results_button.clicked.connect(self.download_results)
        self.download_results_button.setEnabled(False)
        results_buttons_layout.addWidget(self.download_results_button)
        
        results_layout.addLayout(results_buttons_layout)
        
        tab_widget.addTab(results_tab, "Results")
        
        return right_widget

    def load_fasta_file(self):
        """Load a FASTA file through file dialog"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Open FASTA File", "", "FASTA Files (*.fasta *.fa);;All Files (*)")
        
        if file_path:
            self.current_fasta_path = file_path
            self.file_path_label.setText(file_path)
            self.find_roi_button.setEnabled(True)

    def paste_sequence(self):
        """Open a dialog to paste a sequence"""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Paste Sequence")
        dialog.setText("Paste your FASTA sequence below:")
        
        # Create a text edit for input
        text_edit = QTextEdit()
        text_edit.setMinimumSize(400, 200)
        
        # Create a custom layout for the dialog
        layout = QVBoxLayout()
        layout.addWidget(text_edit)
        
        # Get the content widget of the message box
        content_widget = dialog.findChild(QWidget)
        if content_widget:
            content_layout = content_widget.layout()
            if content_layout:
                content_layout.addWidget(text_edit)
        
        # Add OK and Cancel buttons
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        
        # Show the dialog
        result = dialog.exec()
        
        if result == QMessageBox.StandardButton.Ok:
            sequence = text_edit.toPlainText()
            if sequence:
                # Save to a temporary file
                temp_file = "temp_sequence.fasta"
                with open(temp_file, "w") as f:
                    f.write(sequence)
                
                self.current_fasta_path = temp_file
                self.file_path_label.setText("Pasted sequence")
                self.find_roi_button.setEnabled(True)
    
    def find_roi(self):
        """Find the Region of Interest in the loaded FASTA file"""
        if not self.current_fasta_path:
            QMessageBox.warning(self, "Error", "Please load a FASTA file first.")
            return
        
        # Get the ROI pattern
        roi_pattern = self.roi_input.text().strip()
        if not roi_pattern:
            QMessageBox.warning(self, "Error", "Please enter a ROI pattern.")
            return
        
        # Load the FASTA file
        fasta_content = SequenceProcessor.load_fasta_file(self.current_fasta_path)
        if not fasta_content:
            QMessageBox.warning(self, "Error", "Failed to load the FASTA file.")
            return
        
        # Find the ROI
        self.roi_sequence = SequenceProcessor.find_roi_in_fasta(fasta_content, roi_pattern)
        
        if not self.roi_sequence:
            QMessageBox.warning(self, "ROI Not Found", 
                              f"Could not find the pattern '{roi_pattern}' in the sequence.")
            return
        
        # Display the ROI
        self.roi_result.setText(self.roi_sequence)
        self.dna_review.setText(self.roi_sequence)
        
        # Check if we can enable the submit button
        self.update_submit_button()
        
        QMessageBox.information(self, "ROI Found", 
                             f"Found the pattern '{roi_pattern}' in the sequence.\n\n"
                             "The ROI sub-sequence has been extracted and is ready for AlphaFold submission.")
    
    def on_protein_sequence_changed(self):
        """Handle changes to the protein sequence text"""
        self.protein_sequence_text = self.protein_sequence.toPlainText().strip()
        self.protein_review.setText(self.protein_sequence_text)
        self.update_submit_button()
    
    def update_submit_button(self):
        """Update the state of the submit button based on input data"""
        has_roi = self.roi_sequence is not None and len(self.roi_sequence) > 0
        has_protein = self.protein_sequence_text is not None and len(self.protein_sequence_text) > 0
        has_credentials = (self.alphafold_email.text().strip() != "" and 
                          self.alphafold_password.text().strip() != "")
        
        self.submit_button.setEnabled(has_roi and has_protein and has_credentials)

    def submit_to_alphafold(self):
        """Submit the sequence data to AlphaFold 3"""
        # Get credentials
        email = self.alphafold_email.text().strip()
        password = self.alphafold_password.text().strip()
        
        # Get job settings
        job_name = self.job_name_input.text().strip()
        use_multimer = self.multimer_model.isChecked()
        save_all_models = self.save_all_models.isChecked()
        
        # Disable the submit button during submission
        self.submit_button.setEnabled(False)
        self.submit_button.setText("Submitting...")
        
        try:
            # Set up the AlphaFold submitter
            self.alphafold_submitter.setup(
                email=email,
                password=password,
                job_name=job_name,
                dna_sequence=self.roi_sequence,
                protein_sequence=self.protein_sequence_text,
                use_multimer=use_multimer,
                save_all_models=save_all_models
            )
            
            # Start the submission in a separate thread
            submission_success = self.alphafold_submitter.submit_job()
            
            if submission_success:
                # Show success message
                QMessageBox.information(self, "Submission Status", 
                                    "Job has been submitted to AlphaFold 3.\n\n"
                                    "You can check the status in the Results tab.")
                
                # Enable the download results button
                self.download_results_button.setEnabled(True)
                
                # Update the results viewer
                self.results_viewer.setText(f"Job ID: {self.alphafold_submitter.job_id}\n")
                self.results_viewer.append(f"Job Name: {job_name}\n")
                self.results_viewer.append(f"Status: {self.alphafold_submitter.job_status}\n\n")
                self.results_viewer.append("Your job has been submitted and is being processed.")
                self.results_viewer.append("Click 'Refresh Results' to check the current status.")
            else:
                QMessageBox.warning(self, "Submission Failed", 
                                 "Failed to submit the job to AlphaFold 3.\n\n"
                                 "Please check your credentials and internet connection, then try again.")
                
        except Exception as e:
            QMessageBox.critical(self, "Submission Error", 
                              f"An error occurred during submission: {str(e)}")
        finally:
            # Re-enable the submit button
            self.submit_button.setEnabled(True)
            self.submit_button.setText("Submit to AlphaFold 3")
    
    def refresh_results(self):
        """Refresh the results from AlphaFold 3"""
        # Check if we have a job to check
        if not self.alphafold_submitter.job_id:
            QMessageBox.warning(self, "No Job", 
                              "No job has been submitted yet.\n\n"
                              "Please submit a job first.")
            return
        
        # Show a progress message
        self.status_label.setText("Refreshing job status...")
        self.progress_bar.setVisible(True)
        
        try:
            # Check the job status
            status = self.alphafold_submitter.check_job_status()
            
            # Update the results viewer
            self.results_viewer.setText(f"Job ID: {self.alphafold_submitter.job_id}\n")
            self.results_viewer.append(f"Job Name: {self.alphafold_submitter.job_name}\n")
            self.results_viewer.append(f"Status: {status}\n\n")
            
            if status == "Completed":
                self.results_viewer.append("Your AlphaFold 3 job has completed successfully.")
                self.results_viewer.append("Click 'Download Results' to get the PDB files and analysis data.")
                self.download_results_button.setEnabled(True)
            elif status == "Running":
                self.results_viewer.append("Your AlphaFold 3 job is still running. Please check back later.")
                self.download_results_button.setEnabled(False)
            elif status == "Failed":
                self.results_viewer.append("Your AlphaFold 3 job failed. Please try submitting again with different parameters.")
                self.download_results_button.setEnabled(False)
            elif status == "Queued":
                self.results_viewer.append("Your AlphaFold 3 job is queued. The server will start processing it soon.")
                self.download_results_button.setEnabled(False)
            else:
                self.results_viewer.append("Unable to determine job status. Please check the AlphaFold website directly.")
                self.download_results_button.setEnabled(False)
            
            # Show success message
            QMessageBox.information(self, "Refresh Status", 
                                 "Job status has been refreshed.")
                                 
        except Exception as e:
            QMessageBox.warning(self, "Refresh Error", 
                              f"An error occurred while refreshing the job status: {str(e)}")
        finally:
            self.status_label.setText("Ready")
            self.progress_bar.setVisible(False)
    
    def download_results(self):
        """Download the results from AlphaFold 3"""
        # Check if we have a job to download
        if not self.alphafold_submitter.job_id:
            QMessageBox.warning(self, "No Job", 
                              "No job has been submitted yet.\n\n"
                              "Please submit a job first.")
            return
        
        # Create a directory for the results
        output_dir = "alphafold_results"
        os.makedirs(output_dir, exist_ok=True)
        
        # Show a progress message
        self.status_label.setText("Downloading AlphaFold results...")
        self.progress_bar.setVisible(True)
        
        try:
            # Download the results
            success = self.alphafold_submitter.download_results(output_dir)
            
            if success:
                # Get the full path to the results directory
                job_dir = os.path.join(output_dir, self.alphafold_submitter.job_id)
                full_path = os.path.abspath(job_dir)
                
                QMessageBox.information(self, "Download Complete", 
                                     f"AlphaFold 3 results have been downloaded to:\n{full_path}\n\n"
                                     "You can now analyze these files in Discovery Studio.")
                
                # Update the results viewer
                self.results_viewer.append("\nResults downloaded successfully.")
                self.results_viewer.append(f"Results location: {full_path}")
            else:
                QMessageBox.warning(self, "Download Failed", 
                                 "Failed to download the results.\n\n"
                                 "Please check that the job is completed and try again.")
                
        except Exception as e:
            QMessageBox.critical(self, "Download Error", 
                              f"An error occurred during download: {str(e)}")
        finally:
            self.status_label.setText("Ready")
            self.progress_bar.setVisible(False)

    # BULK DOWNLOAD METHODS

    def browse_fasta_directory(self):
        """Browse for directory containing FASTA files"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Directory with FASTA Files",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if directory:
            self.fasta_directory_path = directory
            self.fasta_dir_label.setText(directory)
            self.process_directory_button.setEnabled(True)
            
            # Count FASTA files in directory
            fasta_files = list(Path(directory).glob("*.fasta")) + list(Path(directory).glob("*.fa"))
            self.preprocessing_status.setText(f"Found {len(fasta_files)} FASTA files in directory")
    
    def browse_excel_file(self):
        """Browse for Excel file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Excel File", 
            "", 
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if file_path:
            self.excel_path_label.setText(file_path)
            self.load_excel_button.setEnabled(True)
    
    def browse_output_directory(self):
        """Browse for output directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        
        if dir_path:
            self.output_dir_label.setText(dir_path)
    
    def load_excel_file(self):
        """Load gene list from Excel file"""
        excel_path = self.excel_path_label.text()
        if excel_path == "No file selected":
            QMessageBox.warning(self, "Error", "Please select an Excel file first.")
            return
        
        # Get column settings
        gene_column = self.gene_column_combo.currentIndex()
        
        organism_column = None
        if self.organism_column_combo.currentText() != "None":
            organism_column = self.organism_column_combo.currentIndex() - 1
        
        status_column = None
        if self.status_column_combo.currentText() != "None":
            status_column = self.status_column_combo.currentIndex() - 1
        
        # Start loading thread
        self.excel_load_thread = ExcelLoadThread(
            excel_path, gene_column, organism_column, status_column
        )
        self.excel_load_thread.finished_signal.connect(self.on_excel_loaded)
        self.excel_load_thread.error_signal.connect(self.handle_error)
        self.excel_load_thread.progress_signal.connect(self.update_bulk_status)
        self.excel_load_thread.start()
        
        # Disable load button during loading
        self.load_excel_button.setEnabled(False)
        self.load_excel_button.setText("Loading...")
    
    def on_excel_loaded(self, gene_list):
        """Handle successful Excel loading"""
        self.current_gene_list = gene_list
        self.load_excel_button.setEnabled(True)
        self.load_excel_button.setText("Load Gene List")
        
        # Update gene count
        self.gene_count_label.setText(f"Genes loaded: {len(gene_list)}")
        
        # Populate gene table
        self.populate_gene_table(gene_list)
        
        # Update button state (this will check both genes and email)
        self.update_bulk_download_button_state()
        
        self.update_bulk_status(f"Successfully loaded {len(gene_list)} genes")
    
    def populate_gene_table(self, gene_list):
        """Populate the gene table with loaded genes"""
        self.gene_table.setRowCount(min(len(gene_list), 50))  # Show max 50 rows
        
        for i, gene_info in enumerate(gene_list[:50]):  # Limit display to first 50
            self.gene_table.setItem(i, 0, QTableWidgetItem(gene_info['gene_name']))
            self.gene_table.setItem(i, 1, QTableWidgetItem(gene_info['organism']))
            self.gene_table.setItem(i, 2, QTableWidgetItem(gene_info.get('status', '')))
            self.gene_table.setItem(i, 3, QTableWidgetItem(str(gene_info['row_index'])))
        
        if len(gene_list) > 50:
            self.update_bulk_status(f"Showing first 50 of {len(gene_list)} genes in table")
    
    def start_bulk_download(self):
        """Start the bulk download process"""
        if not self.current_gene_list:
            QMessageBox.warning(self, "Error", "Please load a gene list first.")
            return
        
        email = self.bulk_email_input.text().strip()
        if not email or '@' not in email:
            QMessageBox.warning(self, "Error", "Please enter a valid email address.")
            return
        
        # Get settings
        output_dir = self.output_dir_label.text()
        seq_length = self.bulk_length_input.value()
        delay = self.delay_input.value()
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Start bulk download thread
        self.bulk_download_thread = BulkDownloadThread(
            email, self.current_gene_list, output_dir, seq_length, delay, max_retries=3
        )
        
        self.bulk_download_thread.progress_signal.connect(self.update_bulk_progress)
        self.bulk_download_thread.finished_signal.connect(self.on_bulk_download_finished)
        self.bulk_download_thread.error_signal.connect(self.handle_bulk_error)
        self.bulk_download_thread.start()
        
        # Update UI
        self.start_bulk_button.setEnabled(True)
        self.stop_bulk_button.setEnabled(True)
        self.load_excel_button.setEnabled(False)
        self.update_bulk_status("Starting bulk download...")
        
        # Clear previous log
        self.bulk_log.clear()
    
    def stop_bulk_download(self):
        """Stop the bulk download process"""
        if self.bulk_download_thread:
            self.bulk_download_thread.stop()
            self.update_bulk_status("Stopping bulk download...")
            self.stop_bulk_button.setEnabled(False)
    
    def retry_failed_downloads(self):
        """Retry failed downloads from a previous summary file"""
        summary_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Summary File",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not summary_file:
            return
        
        email = self.bulk_email_input.text().strip()
        if not email or '@' not in email:
            QMessageBox.warning(self, "Error", "Please enter a valid email address.")
            return
        
        output_dir = self.output_dir_label.text()
        
        # Start retry thread
        self.retry_thread = RetryFailedThread(email, summary_file, output_dir)
        self.retry_thread.progress_signal.connect(self.update_bulk_progress)
        self.retry_thread.finished_signal.connect(self.on_retry_finished)
        self.retry_thread.error_signal.connect(self.handle_bulk_error)
        self.retry_thread.start()
        
        # Update UI
        self.retry_failed_button.setEnabled(False)
        self.update_bulk_status("Retrying failed downloads...")
    
    def update_bulk_progress(self, current, total, message):
        """Update bulk download progress"""
        self.bulk_progress_bar.setMaximum(total)
        self.bulk_progress_bar.setValue(current)
        self.update_bulk_status(message)
        
        # Update stats
        downloaded = current
        failed = 0  # This would be updated from the actual thread if needed
        self.bulk_stats_label.setText(f"Downloaded: {downloaded} | Failed: {failed}")
    
    def update_bulk_status(self, message):
        """Update bulk status label and log"""
        self.bulk_status_label.setText(message)
        self.bulk_log.append(f"[{QTimer().remainingTime()}] {message}")
        
        # Auto-scroll to bottom
        scrollbar = self.bulk_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def on_bulk_download_finished(self, summary):
        """Handle bulk download completion"""
        # Reset UI
        self.start_bulk_button.setEnabled(True)
        self.stop_bulk_button.setEnabled(False)
        self.load_excel_button.setEnabled(True)
        self.retry_failed_button.setEnabled(True)
        
        # Update final stats
        successful = summary['successful_downloads']
        failed = summary['failed_downloads']
        total = summary['total_genes']
        
        self.bulk_stats_label.setText(f"Downloaded: {successful} | Failed: {failed}")
        self.update_bulk_status(f"Bulk download completed! {successful}/{total} successful")
        
        # Show completion message
        QMessageBox.information(
            self,
            "Bulk Download Complete",
            f"Bulk download completed!\n\n"
            f"Total genes: {total}\n"
            f"Successful downloads: {successful}\n"
            f"Failed downloads: {failed}\n\n"
            f"Results saved to: {summary['output_directory']}"
        )
    
    def on_retry_finished(self, updated_summary):
        """Handle retry completion"""
        self.retry_failed_button.setEnabled(True)
        
        retry_successful = updated_summary.get('retry_successful', 0)
        still_failed = updated_summary.get('still_failed', 0)
        
        self.update_bulk_status(f"Retry completed! {retry_successful} additional downloads successful")
        
        QMessageBox.information(
            self,
            "Retry Complete",
            f"Retry completed!\n\n"
            f"Additional successful downloads: {retry_successful}\n"
            f"Still failed: {still_failed}"
        )
    
    def handle_bulk_error(self, error_message):
        """Handle bulk download errors"""
        # Reset UI
        self.start_bulk_button.setEnabled(True)
        self.stop_bulk_button.setEnabled(False)
        self.load_excel_button.setEnabled(True)
        self.retry_failed_button.setEnabled(True)
        
        self.update_bulk_status("Error occurred during bulk download")
        
        # Show error dialog
        QMessageBox.critical(self, "Bulk Download Error", error_message)

    def browse_excel_output(self):
        """Browse for Excel output file location"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel Output As",
            "roi_analysis_summary.xlsx",
            "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if file_path:
            self.excel_output_label.setText(file_path)

    def process_fasta_directory(self):
        """Start processing all FASTA files in the selected directory"""
        if not self.fasta_directory_path:
            QMessageBox.warning(self, "Error", "Please select a directory first.")
            return
        
        roi_pattern = self.bulk_roi_input.text().strip()
        if not roi_pattern:
            QMessageBox.warning(self, "Error", "Please enter a ROI pattern.")
            return
        
        # Start processing thread
        self.preprocessing_thread = BulkPreprocessingThread(
            self.fasta_directory_path,
            roi_pattern
        )
        
        self.preprocessing_thread.progress_signal.connect(self.update_preprocessing_progress)
        self.preprocessing_thread.finished_signal.connect(self.on_preprocessing_finished)
        self.preprocessing_thread.error_signal.connect(self.handle_preprocessing_error)
        self.preprocessing_thread.start()
        
        # Update UI
        self.process_directory_button.setText("Processing...")
        self.process_directory_button.setEnabled(False)
        self.preprocessing_status.setText("Starting bulk processing...")

    def update_preprocessing_progress(self, current, total, message):
        """Update preprocessing progress"""
        self.preprocessing_progress.setMaximum(total)
        self.preprocessing_progress.setValue(current)
        self.preprocessing_status.setText(message)
        self.files_processed_label.setText(f"Files processed: {current}")

    def on_preprocessing_finished(self, results_df):
        """Handle completion of bulk preprocessing"""
        self.preprocessing_results_df = results_df
        
        # Update UI
        self.process_directory_button.setText("Process All FASTA Files")
        self.process_directory_button.setEnabled(True)
        self.export_results_button.setEnabled(True)
        
        # Update summary statistics
        total_files = len(results_df['gene_name'].unique())
        total_roi_found = len(results_df[results_df['found_roi'] == True])
        
        self.files_processed_label.setText(f"Files processed: {total_files}")
        self.roi_found_label.setText(f"ROI sequences found: {total_roi_found}")
        self.preprocessing_status.setText(f"Processing complete! {total_roi_found} ROI sequences found in {total_files} files")
        
        # Display preview in table
        self.display_results_preview(results_df)
        
        # Show completion message
        QMessageBox.information(
            self,
            "Processing Complete",
            f"Bulk processing completed successfully!\n\n"
            f"Files processed: {total_files}\n"
            f"ROI sequences found: {total_roi_found}\n\n"
            f"Click 'Export Full Results to Excel' to save the complete analysis."
        )

    def display_results_preview(self, df):
        """Display preview of results in the table widget"""
        # Show first 10 rows
        preview_df = df.head(10)
        
        # Set up table
        self.results_table.setRowCount(len(preview_df))
        self.results_table.setColumnCount(len(preview_df.columns))
        self.results_table.setHorizontalHeaderLabels(list(preview_df.columns))
        
        # Populate table
        for row_idx, (_, row) in enumerate(preview_df.iterrows()):
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                self.results_table.setItem(row_idx, col_idx, item)
        
        # Adjust column widths
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def handle_preprocessing_error(self, error_message):
        """Handle preprocessing errors"""
        # Reset UI
        self.process_directory_button.setText("Process All FASTA Files")
        self.process_directory_button.setEnabled(True)
        self.preprocessing_status.setText("Error occurred during processing")
        
        # Show error dialog
        QMessageBox.critical(
            self,
            "Preprocessing Error",
            f"An error occurred during bulk preprocessing:\n\n{error_message}"
        )

    def create_submission_tab(self):
        """Create the AlphaFold submission tab with job management and login functionality"""
        submission_widget = QWidget()
        submission_layout = QVBoxLayout(submission_widget)
        
        # AlphaFold Login Section (NEW)
        login_group = QGroupBox("AlphaFold 3 Authentication")
        login_layout = QVBoxLayout()
        
        # Login status display
        status_layout = QHBoxLayout()
        self.login_status_label = QLabel("Status: Not logged in")
        self.login_status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.login_status_label)
        status_layout.addStretch()
        login_layout.addLayout(status_layout)

        # 6. ADDED configuration option for screenshots
        screenshot_layout = QHBoxLayout()
        self.capture_screenshots = QCheckBox("Capture screenshots of results pages")
        self.capture_screenshots.setChecked(True)  # Default to enabled
        self.capture_screenshots.setToolTip("Automatically take screenshots of AlphaFold results pages")
        screenshot_layout.addWidget(self.capture_screenshots)
        screenshot_layout.addStretch()

        # Add info about screenshots
        screenshot_info = QLabel("Screenshots will be saved with the same name as the job in the download directory")
        screenshot_info.setStyleSheet("color: #666; font-size: 10px;")
        screenshot_info.setWordWrap(True)
        
        # Login buttons
        login_buttons_layout = QHBoxLayout()
        
        self.manual_login_button = QPushButton("Manual Login & Save Cookies")
        self.manual_login_button.clicked.connect(self.perform_manual_login)
        self.manual_login_button.setMinimumHeight(35)
        self.manual_login_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        login_buttons_layout.addWidget(self.manual_login_button)
        
        self.auto_login_button = QPushButton("Login with Saved Cookies")
        self.auto_login_button.clicked.connect(self.perform_auto_login)
        self.auto_login_button.setMinimumHeight(35)
        self.auto_login_button.setEnabled(False)
        login_buttons_layout.addWidget(self.auto_login_button)
        
        self.check_login_button = QPushButton("Check Login Status")
        self.check_login_button.clicked.connect(self.check_login_status)
        login_buttons_layout.addWidget(self.check_login_button)
        
        login_layout.addLayout(login_buttons_layout)
        
        # Login instructions
        instructions = QLabel(
            "Instructions:\n"
            "1. First time: Click 'Manual Login & Save Cookies' and complete Google login in browser\n"
            "2. Future logins: Click 'Login with Saved Cookies' for automatic authentication\n"
            "3. If cookies expire, repeat step 1"
        )
        instructions.setStyleSheet("color: #666; font-size: 11px; margin: 10px;")
        instructions.setWordWrap(True)
        login_layout.addWidget(instructions)
        
        login_group.setLayout(login_layout)
        submission_layout.addWidget(login_group)
        
        # ROI Data Loading Section
        roi_group = QGroupBox("ROI Data Configuration")
        roi_layout = QVBoxLayout()
        
        # ROI Excel file selection
        roi_file_layout = QHBoxLayout()
        self.roi_excel_label = QLabel("No ROI file selected")
        self.browse_roi_excel_button = QPushButton("Browse ROI Excel")
        self.browse_roi_excel_button.clicked.connect(self.browse_roi_excel_file)
        roi_file_layout.addWidget(QLabel("ROI Excel File:"))
        roi_file_layout.addWidget(self.roi_excel_label)
        roi_file_layout.addWidget(self.browse_roi_excel_button)
        roi_layout.addLayout(roi_file_layout)
        
        # ROI info
        self.roi_count_label = QLabel("ROI sequences loaded: 0")
        roi_layout.addWidget(self.roi_count_label)
        
        roi_group.setLayout(roi_layout)
        submission_layout.addWidget(roi_group)
        
        # Job Management Section
        
        # Download Configuration Section (NEW)
        download_group = QGroupBox("Download Configuration")
        download_layout = QVBoxLayout()

        # Download directory selection
        download_dir_layout = QHBoxLayout()
        download_dir_layout.addWidget(QLabel("Download Directory:"))
        self.download_dir_label = QLabel("No directory selected")
        self.download_dir_label.setStyleSheet("border: 1px solid #ccc; padding: 5px; background-color: #f9f9f9;")
        download_dir_layout.addWidget(self.download_dir_label)

        self.browse_download_dir_button = QPushButton("Browse")
        self.browse_download_dir_button.clicked.connect(self.browse_download_directory)
        download_dir_layout.addWidget(self.browse_download_dir_button)

        download_layout.addLayout(download_dir_layout)

        # Download settings
        download_settings_layout = QHBoxLayout()

        # Job timeout setting
        download_settings_layout.addWidget(QLabel("Job Timeout:"))
        self.job_timeout_input = QSpinBox()
        self.job_timeout_input.setRange(30, 300)  # 30 minutes to 5 hours
        self.job_timeout_input.setValue(120)  # Default 2 hours
        self.job_timeout_input.setSuffix(" minutes")
        download_settings_layout.addWidget(self.job_timeout_input)

        # Status check interval
        download_settings_layout.addWidget(QLabel("Check Interval:"))
        self.status_check_interval = QSpinBox()
        self.status_check_interval.setRange(1, 30)  # 1 to 30 minutes
        self.status_check_interval.setValue(5)  # Default 5 minutes
        self.status_check_interval.setSuffix(" minutes")
        download_settings_layout.addWidget(self.status_check_interval)

        download_settings_layout.addStretch()
        download_layout.addLayout(download_settings_layout)

        # Download status
        download_status_layout = QHBoxLayout()
        self.download_status_label = QLabel("Download folder: Not configured")
        self.download_status_label.setStyleSheet("color: #666; font-size: 11px;")
        download_status_layout.addWidget(self.download_status_label)
        download_status_layout.addStretch()

        # Auto-open downloads folder checkbox
        self.auto_open_downloads = QCheckBox("Open downloads folder when batch completes")
        self.auto_open_downloads.setChecked(True)
        download_status_layout.addWidget(self.auto_open_downloads)

        download_layout.addLayout(download_status_layout)

        download_group.setLayout(download_layout)
        submission_layout.addWidget(download_group)

        # Initialize download directory variable
        self.download_directory = None

        job_group = QGroupBox("Batch Job Management")
        job_layout = QVBoxLayout()
        
        # Job limit and validation
        limit_layout = QHBoxLayout()
        limit_layout.addWidget(QLabel("Daily Job Limit:"))
        self.job_limit_input = QSpinBox()
        self.job_limit_input.setRange(1, 100)
        self.job_limit_input.setValue(30)
        limit_layout.addWidget(self.job_limit_input)
        limit_layout.addWidget(QLabel("jobs per day"))
        
        # Add validation button
        self.validate_setup_button = QPushButton("Validate Setup")
        self.validate_setup_button.clicked.connect(self.validate_current_setup)
        self.validate_setup_button.setEnabled(False)  # Disabled until logged in
        limit_layout.addWidget(self.validate_setup_button)
        limit_layout.addStretch()
        job_layout.addLayout(limit_layout)
        
        # Job summary
        summary_layout = QHBoxLayout()
        self.total_jobs_label = QLabel("Total jobs to submit: 0")
        self.jobs_completed_label = QLabel("Jobs completed: 0")
        summary_layout.addWidget(self.total_jobs_label)
        summary_layout.addWidget(self.jobs_completed_label)
        summary_layout.addStretch()
        job_layout.addLayout(summary_layout)
        
        # Export and batch controls
        controls_layout = QHBoxLayout()
        
        self.export_plan_button = QPushButton("Export Job Plan")
        self.export_plan_button.clicked.connect(self.export_job_plan)
        self.export_plan_button.setEnabled(False)
        controls_layout.addWidget(self.export_plan_button)
        
        self.start_batch_button = QPushButton("Start Batch Submission")
        self.start_batch_button.clicked.connect(self.start_batch_submission)
        self.start_batch_button.setEnabled(False)
        self.start_batch_button.setMinimumHeight(40)
        self.start_batch_button.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        controls_layout.addWidget(self.start_batch_button)
        
        self.stop_batch_button = QPushButton("Stop Batch")
        self.stop_batch_button.clicked.connect(self.stop_batch_submission)
        self.stop_batch_button.setEnabled(False)
        controls_layout.addWidget(self.stop_batch_button)
        
        self.resume_batch_button = QPushButton("Resume Batch")
        self.resume_batch_button.clicked.connect(self.resume_batch_submission)
        self.resume_batch_button.setEnabled(False)
        controls_layout.addWidget(self.resume_batch_button)
        
        job_layout.addLayout(controls_layout)
        
        job_group.setLayout(job_layout)
        submission_layout.addWidget(job_group)
        
        # Progress Section
        progress_group = QGroupBox("Batch Progress")
        progress_layout = QVBoxLayout()
        
        # Progress bar
        self.batch_progress_bar = QProgressBar()
        progress_layout.addWidget(self.batch_progress_bar)
        
        # Status and current job info
        status_layout = QHBoxLayout()
        self.batch_status_label = QLabel("Ready for batch submission")
        self.current_job_label = QLabel("Current job: None")
        status_layout.addWidget(self.batch_status_label)
        status_layout.addWidget(self.current_job_label)
        progress_layout.addLayout(status_layout)
        
        # Batch log with controls
        log_controls_layout = QHBoxLayout()
        log_controls_layout.addWidget(QLabel("Batch Log:"))
        log_controls_layout.addStretch()
        
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(lambda: self.batch_log.clear())
        log_controls_layout.addWidget(self.clear_log_button)
        
        self.save_log_button = QPushButton("Save Log")
        self.save_log_button.clicked.connect(self.save_batch_log)
        log_controls_layout.addWidget(self.save_log_button)
        
        progress_layout.addLayout(log_controls_layout)
        
        self.batch_log = QTextEdit()
        self.batch_log.setReadOnly(True)
        self.batch_log.setMaximumHeight(200)
        progress_layout.addWidget(self.batch_log)
        
        progress_group.setLayout(progress_layout)
        submission_layout.addWidget(progress_group)
        
        # Initialize variables
        self.roi_data = []
        self.batch_jobs = []
        self.current_job_index = 0
        self.batch_handler = None
        self.alphafold_login_handler = None  # NEW: Store login handler
        self.is_logged_in = False  # NEW: Track login status
        
        # Check if cookies exist on startup
        self.check_existing_cookies()
        
        return submission_widget

    # 2. FIXED export_preprocessing_results function in ncbi_alphafold_gui_r.py
    def export_preprocessing_results(self):
        """Export the full preprocessing results to Excel (append to existing file)"""
        if self.preprocessing_results_df is None:
            QMessageBox.warning(self, "Error", "No results to export. Please process files first.")
            return
        
        # Get output file path
        output_path = self.excel_output_label.text()
        
        # If it's still the default name, ask user to choose location
        if output_path == "roi_analysis_summary.xlsx":
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Results As",
                "roi_analysis_summary.xlsx",
                "Excel Files (*.xlsx);;All Files (*)"
            )
            
            if not output_path:
                return
        
        try:
            # Check if file already exists
            existing_df = None
            if os.path.exists(output_path):
                try:
                    # Read existing data from ROI_Analysis sheet
                    existing_df = pd.read_excel(output_path, sheet_name='ROI_Analysis')
                    print(f"Found existing file with {len(existing_df)} rows")
                except Exception as e:
                    print(f"Could not read existing file: {e}")
                    existing_df = None
            
            # Prepare final dataframe
            if existing_df is not None and not existing_df.empty:
                # Append new results to the top of existing data
                final_df = pd.concat([self.preprocessing_results_df, existing_df], ignore_index=True)
                print(f"Appending {len(self.preprocessing_results_df)} new rows to {len(existing_df)} existing rows")
            else:
                # No existing data, use new results only
                final_df = self.preprocessing_results_df
                print(f"Creating new file with {len(final_df)} rows")
            
            # Save to Excel with additional summary sheet
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # Main results (with appended data)
                final_df.to_excel(writer, sheet_name='ROI_Analysis', index=False)
                
                # Summary statistics (for all data including existing)
                total_files = len(final_df['gene_name'].unique())
                total_roi_found = len(final_df[final_df['found_roi'] == True])
                files_with_roi = len(final_df[final_df['found_roi'] == True]['gene_name'].unique())
                files_without_roi = len(final_df[final_df['found_roi'] == False]['gene_name'].unique())
                
                # Calculate average ROI per file safely
                avg_roi_per_file = 0
                if total_files > 0:
                    avg_roi_per_file = round(total_roi_found / total_files, 2)
                
                summary_stats = {
                    'Metric': [
                        'Total Files Processed',
                        'Total ROI Sequences Found',
                        'Files with ROI Found',
                        'Files without ROI',
                        'Average ROI per File',
                        'Last Processing Date'
                    ],
                    'Value': [
                        total_files,
                        total_roi_found,
                        files_with_roi,
                        files_without_roi,
                        avg_roi_per_file,
                        pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                    ]
                }
                summary_df = pd.DataFrame(summary_stats)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Show success message
            if existing_df is not None and not existing_df.empty:
                message = (f"Results successfully appended to existing file:\n{output_path}\n\n"
                        f"New entries added: {len(self.preprocessing_results_df)}\n"
                        f"Total entries now: {len(final_df)}\n\n"
                        f"The file contains two sheets:\n"
                        f"- 'ROI_Analysis': All results (new + existing)\n"
                        f"- 'Summary': Updated statistics overview")
            else:
                message = (f"Results successfully exported to:\n{output_path}\n\n"
                        f"Total entries: {len(final_df)}\n\n"
                        f"The file contains two sheets:\n"
                        f"- 'ROI_Analysis': Detailed results\n"
                        f"- 'Summary': Statistics overview")
            
            QMessageBox.information(self, "Export Complete", message)
            
            # Update the label to show the actual saved path
            self.excel_output_label.setText(output_path)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Error saving results to Excel:\n\n{str(e)}"
            )
    
    ######################################### New Code~~~~~~~~~~~~~~~~~~~~
    def browse_protein_excel_file(self):
        """Browse for protein Excel file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Protein Excel File", 
            "", 
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if file_path:
            self.protein_excel_label.setText(file_path)
            self.load_protein_excel_button.setEnabled(True)

    def load_protein_excel_file(self):
        """Load protein sequences from Excel file"""
        excel_path = self.protein_excel_label.text()
        if excel_path == "No file selected":
            QMessageBox.warning(self, "Error", "Please select a protein Excel file first.")
            return
        
        try:
            # Get column indices
            name_col = self.protein_name_column_combo.currentIndex()
            seq_col = self.protein_seq_column_combo.currentIndex()
            
            # Read Excel file
            df = pd.read_excel(excel_path)
            
            # Extract protein data
            self.protein_data = []
            for index, row in df.iterrows():
                protein_name = str(row.iloc[name_col]).strip() if pd.notna(row.iloc[name_col]) else None
                protein_seq = str(row.iloc[seq_col]).strip() if pd.notna(row.iloc[seq_col]) else None
                
                if protein_name and protein_seq and protein_name.lower() not in ['nan', 'none', '']:
                    self.protein_data.append({
                        'name': protein_name,
                        'sequence': protein_seq,
                        'length': len(protein_seq.replace(' ', ''))
                    })
            
            # Update UI
            self.protein_count_label.setText(f"Proteins loaded: {len(self.protein_data)}")
            self.create_protein_radio_buttons()
            self.update_batch_submit_button()
            
            QMessageBox.information(
                self, 
                "Success", 
                f"Successfully loaded {len(self.protein_data)} protein sequences."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading protein Excel file:\n{str(e)}")

    def create_protein_radio_buttons(self):
        """Create radio buttons for protein selection"""
        # Clear existing radio buttons
        for button in self.protein_radio_group.buttons():
            self.protein_radio_group.removeButton(button)
            button.deleteLater()
        
        # Clear layout
        while self.protein_radio_layout.count():
            item = self.protein_radio_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Create new radio buttons
        for i, protein in enumerate(self.protein_data):
            radio = QRadioButton(f"{protein['name']} ({protein['length']} AA)")
            radio.setProperty("protein_index", i)
            radio.toggled.connect(self.on_protein_selection_changed)
            
            self.protein_radio_layout.addWidget(radio)
            self.protein_radio_group.addButton(radio)
            
            # Select first protein by default
            if i == 0:
                radio.setChecked(True)
                self.selected_protein = protein

    def on_protein_selection_changed(self):
        """Handle protein selection change"""
        sender = self.sender()
        if sender.isChecked():
            protein_index = sender.property("protein_index")
            self.selected_protein = self.protein_data[protein_index]
            
            # Update preview
            self.selected_protein_name_label.setText(f"Name: {self.selected_protein['name']}")
            self.selected_protein_length_label.setText(f"Length: {self.selected_protein['length']} AA")
            
            # Show sequence preview (first 100 characters)
            seq_preview = self.selected_protein['sequence'][:100]
            if len(self.selected_protein['sequence']) > 100:
                seq_preview += "..."
            self.protein_sequence_preview.setText(seq_preview)
            
            self.update_batch_submit_button()

    def browse_roi_excel_file(self):
        """Browse for ROI Excel file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select ROI Excel File", 
            "", 
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if file_path:
            self.roi_excel_label.setText(file_path)
            self.load_roi_data()

    def load_roi_data(self):
        """Load ROI data from Excel file"""
        excel_path = self.roi_excel_label.text()
        if excel_path == "No ROI file selected":
            return
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_path, sheet_name='ROI_Analysis')
            
            # Filter rows where found_roi is True
            roi_df = df[df['found_roi'] == True].copy()
            
            # Extract ROI data
            self.roi_data = []
            for _, row in roi_df.iterrows():
                if pd.notna(row['gene']) and pd.notna(row['gene_name']) and pd.notna(row['roi_locus']):
                    self.roi_data.append({
                        'gene_name': str(row['gene_name']),
                        'roi_sequence': str(row['gene']),
                        'roi_locus': str(row['roi_locus']),
                        'accession': str(row.get('accession_number', 'Unknown'))
                    })
            
            # Update UI
            self.roi_count_label.setText(f"ROI sequences loaded: {len(self.roi_data)}")
            self.update_batch_submit_button()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading ROI data:\n{str(e)}")

    # Updated the existing update_batch_submit_button method to also enable export button
    def update_batch_submit_button(self):
        """Updated the batch submit button state (modified to include login check)"""
        has_protein = self.selected_protein is not None
        has_roi = len(self.roi_data) > 0
        is_logged_in = self.is_logged_in  # NEW: Check login status
        
        can_submit = has_protein and has_roi and is_logged_in
        self.start_batch_button.setEnabled(can_submit)
        
        # Enable export button if we have protein and ROI data
        can_export = has_protein and has_roi
        self.export_plan_button.setEnabled(can_export)
        
        # Update job count and prepare batch jobs for export
        if has_protein and has_roi:
            try:
                selected_protein_index = self.protein_data.index(self.selected_protein)
                job_limit = self.job_limit_input.value()
                from protein_roi_loader import create_job_batch
                self.batch_jobs, _ = create_job_batch(
                    self.protein_data, 
                    self.roi_data, 
                    selected_protein_index, 
                    job_limit
                )
                total_jobs = len(self.batch_jobs)
                self.total_jobs_label.setText(f"Total jobs to submit: {total_jobs}")
            except Exception:
                self.total_jobs_label.setText("Total jobs to submit: 0")
        else:
            self.total_jobs_label.setText("Total jobs to submit: 0")
            self.batch_jobs = []
        
        # Update status message based on what's missing
        if not is_logged_in:
            self.batch_status_label.setText("Please login to AlphaFold 3 first")
        elif not has_protein:
            self.batch_status_label.setText("Please select a protein sequence")
        elif not has_roi:
            self.batch_status_label.setText("Please load ROI data")
        else:
            self.batch_status_label.setText("Ready for batch submission")

    def start_batch_submission(self):
        """Start the batch submission process with AlphaFold automation"""
        try:
            # Validate all requirements
            if not self._validate_batch_requirements():
                return
            
            # Get download configuration
            download_config = self.get_download_configuration()
            
            # Validate download configuration
            download_valid, download_msg = self.validate_download_configuration()
            if not download_valid:
                QMessageBox.critical(self, "Download Configuration Error", download_msg)
                return
            
            # Prepare batch jobs
            self.prepare_batch_jobs()
            
            # Check job limit
            job_limit = self.job_limit_input.value()
            if len(self.batch_jobs) > job_limit:
                reply = QMessageBox.question(
                    self,
                    "Job Limit Warning",
                    f"You have {len(self.batch_jobs)} jobs to submit but your daily limit is {job_limit}.\n"
                    f"Do you want to submit only the first {job_limit} jobs?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.batch_jobs = self.batch_jobs[:job_limit]
                else:
                    return
            
            # Initialize progress tracking
            self.current_job_index = 0
            self.successful_jobs = []
            self.failed_jobs = []
            
            # Update UI state
            self._set_batch_ui_state(processing=True)
            
            # Log batch start
            self.batch_log.append("="*50)
            self.batch_log.append(f"STARTING BATCH SUBMISSION")
            self.batch_log.append(f"Protein: {self.selected_protein['name']}")
            self.batch_log.append(f"Total jobs: {len(self.batch_jobs)}")
            self.batch_log.append(f"Download directory: {download_config['download_directory']}")
            self.batch_log.append(f"Job timeout: {download_config['job_timeout_minutes']} minutes")
            self.batch_log.append("="*50)
            
            self.batch_handler = AlphaFoldJobHandler(
                login_handler=self.alphafold_login_handler,
                download_config=download_config
            )
            
            # Connect signals for real-time updates
            self.batch_handler.progress_update.connect(self.on_automation_progress)
            self.batch_handler.job_started.connect(self.on_automation_job_started)
            self.batch_handler.job_completed.connect(self.on_automation_job_completed_with_screenshot)
            self.batch_handler.job_failed.connect(self.on_automation_job_failed)
            self.batch_handler.batch_completed.connect(self.on_automation_batch_completed)
            self.batch_handler.job_progress.connect(self.on_automation_job_progress)

            # Add info about screenshots
            screenshot_info = QLabel("Screenshots will be saved with the same name as the job in the download directory")
            screenshot_info.setStyleSheet("color: #666; font-size: 10px;")
            screenshot_info.setWordWrap(True)
                        
            # Set jobs and start processing
            self.batch_handler.set_jobs(self.batch_jobs)
            self.batch_handler.start()
            
            self.batch_log.append("✓ AlphaFold automation started successfully")
            self.batch_log.append("📸 Screenshots will be captured for each completed job")
            
        except Exception as e:
            self._handle_batch_error(f"Error starting batch submission: {str(e)}")

    # 2. ADD new signal handler method for job completion with screenshot
    def on_automation_job_completed_with_screenshot(self, job_name, job_id, download_path, screenshot_path):
        """Handle job completed signal with screenshot information"""
        self.current_job_index += 1
        self.jobs_completed_label.setText(f"Jobs completed: {self.current_job_index}")
        
        # Store successful job info with screenshot
        job_info = {
            'name': job_name,
            'id': job_id,
            'download_path': download_path,
            'screenshot_path': screenshot_path,
            'completed_time': datetime.now().isoformat()
        }
        self.successful_jobs.append(job_info)
        
        # Log completion with screenshot info
        self.batch_log.append(f"Completed: {job_name}")
        self.batch_log.append(f"   Downloaded: {download_path}")
        
        if screenshot_path and screenshot_path != 'No screenshot':
            self.batch_log.append(f"   Screenshot: {screenshot_path}")
        else:
            self.batch_log.append(f"   Screenshot could not be taken")
    
    def prepare_batch_jobs(self):
        """Prepare the list of jobs for batch submission (Updated)"""
        self.batch_jobs = []
        
        for roi in self.roi_data:
            # Generate job name with more precise timestamp
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            
            # Create job name: Protein-DNA_ProteinName_GeneName_Locus_Timestamp
            job_name = f"Protein-DNA_{self.selected_protein['name']}_{roi['gene_name']}_{roi['roi_locus']}_{timestamp}"
            
            # Ensure job name is valid for AlphaFold (remove invalid characters)
            import re
            job_name = re.sub(r'[^\w\-_\.: ]', '_', job_name)
            
            job = {
                'job_name': job_name,
                'protein_name': self.selected_protein['name'],
                'protein_sequence': self.selected_protein['sequence'],
                'dna_sequence': roi['roi_sequence'],
                'gene_name': roi['gene_name'],
                'roi_locus': roi['roi_locus'],
                'accession': roi.get('accession', 'Unknown'),
                'created_time': datetime.now().isoformat()
            }
            
            self.batch_jobs.append(job)
        
        self.batch_log.append(f"Prepared {len(self.batch_jobs)} jobs for submission")

    def _validate_batch_requirements(self):
        """Validate all requirements for batch submission"""
        # Check protein selection
        if not self.selected_protein:
            QMessageBox.warning(self, "Missing Protein", "Please select a protein sequence first.")
            return False
        
        # Check ROI data
        if not self.roi_data:
            QMessageBox.warning(self, "Missing ROI Data", "Please load ROI data first.")
            return False
        
        # Check login status
        if not self.is_logged_in:
            QMessageBox.warning(self, "Not Logged In", "Please login to AlphaFold 3 first.")
            return False
        
        # Check if login handler has active session
        if not self.alphafold_login_handler or not hasattr(self.alphafold_login_handler, 'driver'):
            QMessageBox.warning(self, "Login Session Error", 
                            "No active login session found. Please login again.")
            return False
        
        return True
    
    def _set_batch_ui_state(self, processing=False):
        """Set UI state for batch processing"""
        # Update button states
        self.start_batch_button.setEnabled(not processing)
        self.stop_batch_button.setEnabled(processing)
        self.resume_batch_button.setEnabled(False)
        
        # Update other controls
        self.validate_setup_button.setEnabled(not processing)
        self.export_plan_button.setEnabled(not processing)
        self.manual_login_button.setEnabled(not processing)
        self.auto_login_button.setEnabled(not processing)
        
        if processing:
            self.batch_status_label.setText("Processing batch jobs...")
            self.start_batch_button.setText("Processing...")
        else:
            self.batch_status_label.setText("Ready for batch submission")
            self.start_batch_button.setText("Start Batch Submission")

    def _handle_batch_error(self, error_message):
        """Handle batch processing errors"""
        # Reset UI state
        self._set_batch_ui_state(processing=False)
        self.resume_batch_button.setEnabled(True)
        
        # Log error
        self.batch_log.append(f"💥 ERROR: {error_message}")
        
        # Show error dialog
        QMessageBox.critical(self, "Batch Processing Error", error_message)

    def on_automation_progress(self, message):
        """Handle progress updates from automation"""
        self.batch_log.append(f"[INFO] {message}")
        
        # Auto-scroll to bottom
        scrollbar = self.batch_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_automation_job_started(self, job_name, job_id):
        """Handle job started signal"""
        self.current_job_label.setText(f"Current: {job_name}")
        self.batch_log.append(f"🚀 Started: {job_name} (ID: {job_id})")

    def on_automation_job_completed(self, job_name, job_id, download_path):
        """Handle job completed signal"""
        self.current_job_index += 1
        self.jobs_completed_label.setText(f"Jobs completed: {self.current_job_index}")
        
        # Store successful job info
        self.successful_jobs.append({
            'name': job_name,
            'id': job_id,
            'download_path': download_path,
            'completed_time': datetime.now().isoformat()
        })
        
        self.batch_log.append(f"✅ Completed: {job_name}")
        self.batch_log.append(f"   Downloaded: {download_path}")

    def on_automation_job_failed(self, job_name, error_message):
        """Handle job failed signal"""
        self.current_job_index += 1
        self.jobs_completed_label.setText(f"Jobs processed: {self.current_job_index}")
        
        # Store failed job info
        self.failed_jobs.append({
            'name': job_name,
            'error': error_message,
            'failed_time': datetime.now().isoformat()
        })
        
        self.batch_log.append(f"  Failed: {job_name}")
        self.batch_log.append(f"   Error: {error_message}")

    # 3. UPDATED the batch completion handler to include screenshot info
    def on_automation_batch_completed(self, summary):
        """Handle batch completion signal with enhanced screenshot reporting"""
        # Reset UI state
        self._set_batch_ui_state(processing=False)
        
        # Update final status
        self.batch_status_label.setText("Batch completed!")
        self.current_job_label.setText("All jobs processed")
        
        # Calculate screenshot statistics
        total_screenshots = 0
        failed_screenshots = 0
        
        for job in self.successful_jobs:
            if job.get('screenshot_path'):
                if job['screenshot_path'] != 'No screenshot':
                    total_screenshots += 1
                else:
                    failed_screenshots += 1
            else:
                failed_screenshots += 1
        
        # Log final summary with screenshot info
        successful = summary.get('successful_jobs', 0)
        failed = summary.get('failed_jobs', 0)
        total = summary.get('total_jobs', 0)
        success_rate = summary.get('success_rate', 0)
        
        self.batch_log.append("="*50)
        self.batch_log.append("BATCH COMPLETED!")
        self.batch_log.append(f"Total jobs: {total}")
        self.batch_log.append(f"Successful: {successful}")
        self.batch_log.append(f"Failed: {failed}")
        self.batch_log.append(f"Success rate: {success_rate:.1f}%")
        self.batch_log.append(f"Screenshots taken: {total_screenshots}")
        if failed_screenshots > 0:
            self.batch_log.append(f"Screenshots failed: {failed_screenshots}")
        self.batch_log.append("="*50)
        
        # Show completion dialog with screenshot info
        completion_message = (
            f"Batch processing completed!\n\n"
            f"Protein: {self.selected_protein['name']}\n"
            f"Total jobs: {total}\n"
            f"Successful: {successful}\n"
            f"Failed: {failed}\n"
            f"Success rate: {success_rate:.1f}%\n"
            f"Screenshots captured: {total_screenshots}/{successful}\n\n"
            f"Results saved to: {self.download_directory}\n\n"
            f"Check the batch log for detailed information."
        )
        
        QMessageBox.information(self, "Batch Complete", completion_message)
        
        # Open downloads folder if requested
        download_config = self.get_download_configuration()
        if download_config.get('auto_open_downloads', False):
            try:
                import subprocess
                import platform
                
                if platform.system() == "Windows":
                    subprocess.Popen(f'explorer "{self.download_directory}"')
                elif platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", self.download_directory])
                else:  # Linux
                    subprocess.Popen(["xdg-open", self.download_directory])
            except Exception as e:
                self.batch_log.append(f"Could not open downloads folder: {str(e)}")

    # 4. ADDED method to view screenshots (optional enhancement)
    def view_job_screenshot(self, job_info):
        """Open screenshot for a specific job (if available)"""
        try:
            screenshot_path = job_info.get('screenshot_path')
            
            if not screenshot_path or screenshot_path == 'No screenshot':
                QMessageBox.warning(self, "No Screenshot", 
                                f"No screenshot available for job: {job_info['name']}")
                return
            
            if not os.path.exists(screenshot_path):
                QMessageBox.warning(self, "Screenshot Not Found", 
                                f"Screenshot file not found: {screenshot_path}")
                return
            
            # Try to open screenshot with default image viewer
            
            if platform.system() == "Windows":
                subprocess.Popen(f'start "" "{screenshot_path}"', shell=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", screenshot_path])
            else:  # Linux
                subprocess.Popen(["xdg-open", screenshot_path])
                
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                            f"Could not open screenshot: {str(e)}")


    def on_automation_job_progress(self, current_job, total_jobs, current_status):
        """Handle job progress updates"""
        # Update progress bar
        self.batch_progress_bar.setMaximum(total_jobs)
        self.batch_progress_bar.setValue(current_job)
        
        # Update status
        progress_percent = int((current_job / total_jobs) * 100) if total_jobs > 0 else 0
        self.batch_status_label.setText(f"Processing job {current_job}/{total_jobs} ({progress_percent}%)")

    # 5. UPDATE validate_current_setup method - ADD download validation:
    def validate_current_setup(self):
        """Validate the current protein and ROI setup before submission"""
        validation_messages = []
        
        # Check protein selection
        if not self.selected_protein:
            validation_messages.append("❌ No protein selected")
        else:
            validation_messages.append(f"✓ Protein: {self.selected_protein['name']} ({self.selected_protein['length']} AA)")
            if self.selected_protein.get('warnings'):
                validation_messages.append(f"  ⚠️ Warnings: {len(self.selected_protein['warnings'])}")
        
        # Check ROI data
        if not self.roi_data:
            validation_messages.append("❌ No ROI data loaded")
        else:
            validation_messages.append(f"✓ ROI sequences: {len(self.roi_data)}")
            valid_rois = [roi for roi in self.roi_data if roi.get('is_valid', True)]
            if len(valid_rois) != len(self.roi_data):
                validation_messages.append(f"  ⚠️ {len(self.roi_data) - len(valid_rois)} ROI sequences have warnings")
        
        # Check login status
        if self.is_logged_in:
            validation_messages.append("✓ Logged in to AlphaFold 3")
        else:
            validation_messages.append("❌ Not logged in to AlphaFold 3")
        
        # Check download configuration (NEW)
        download_valid, download_msg = self.validate_download_configuration()
        if download_valid:
            validation_messages.append(f"✓ Download directory: {self.download_directory}")
            config = self.get_download_configuration()
            validation_messages.append(f"✓ Job timeout: {config['job_timeout_minutes']} minutes")
            validation_messages.append(f"✓ Status check interval: {config['status_check_interval_minutes']} minutes")
        else:
            validation_messages.append(f"❌ Download configuration: {download_msg}")
        
        # Calculate job estimates
        if self.selected_protein and self.roi_data:
            total_jobs = len(self.roi_data)
            job_limit = self.job_limit_input.value()
            
            validation_messages.append(f"📊 Total jobs planned: {total_jobs}")
            validation_messages.append(f"📊 Daily job limit: {job_limit}")
            
            if total_jobs > job_limit:
                validation_messages.append(f"⚠️ Jobs exceed daily limit by {total_jobs - job_limit}")
            
            # Estimate processing time
            estimated_hours = total_jobs * 0.5  # Rough estimate: 30 minutes per job
            validation_messages.append(f"⏱️ Estimated total processing time: {estimated_hours:.1f} hours")
        
        # Show validation dialog
        validation_text = "\n".join(validation_messages)
        QMessageBox.information(self, "Setup Validation", validation_text)

    def stop_batch_submission(self):
        """Stop the batch submission process - FIXED VERSION"""
        try:
            if self.batch_handler:
                # Check if the handler has the stop_batch method
                if hasattr(self.batch_handler, 'stop_batch'):
                    self.batch_handler.stop_batch()
                elif hasattr(self.batch_handler, 'stop_processing'):
                    self.batch_handler.stop_processing()
                else:
                    # Fallback: set should_stop flag if it exists
                    if hasattr(self.batch_handler, 'should_stop'):
                        self.batch_handler.should_stop = True
                    
                    # Try to terminate the thread
                    if hasattr(self.batch_handler, 'terminate'):
                        self.batch_handler.terminate()
            
            # Update UI state regardless of handler method availability
            self.start_batch_button.setEnabled(True)
            self.stop_batch_button.setEnabled(False)
            self.resume_batch_button.setEnabled(True)
            
            # Update status
            self.batch_status_label.setText("Batch submission stopped by user")
            self.current_job_label.setText("Stopped")
            
            # Log the stop action
            self.batch_log.append("⏹️ Batch submission stopped by user")
            
            print("Batch submission stopped successfully")
            
        except Exception as e:
            error_msg = f"Error stopping batch submission: {str(e)}"
            print(error_msg)
            self.batch_log.append(f"⚠️ {error_msg}")
            
            # Still update UI to prevent getting stuck
            self.start_batch_button.setEnabled(True)
            self.stop_batch_button.setEnabled(False)
            self.resume_batch_button.setEnabled(True)
            self.batch_status_label.setText("Error stopping batch - manual intervention may be required")

    def resume_batch_submission(self):
        """Resume the batch submission process - IMPROVED VERSION"""
        try:
            if self.batch_handler and self.current_job_index < len(self.batch_jobs):
                remaining_jobs = self.batch_jobs[self.current_job_index:]
                
                # Check if handler has the right method
                if hasattr(self.batch_handler, 'start_batch'):
                    self.batch_handler.start_batch(remaining_jobs)
                elif hasattr(self.batch_handler, 'set_jobs'):
                    self.batch_handler.set_jobs(remaining_jobs)
                    if hasattr(self.batch_handler, 'start'):
                        self.batch_handler.start()
                else:
                    # Create a new handler if the current one doesn't work
                    self._restart_batch_with_remaining_jobs(remaining_jobs)
                    return
                
                # Update UI
                self.start_batch_button.setEnabled(False)
                self.stop_batch_button.setEnabled(True)
                self.resume_batch_button.setEnabled(False)
                
                self.batch_log.append(f"🔄 Resumed batch submission with {len(remaining_jobs)} remaining jobs")
                
            else:
                self.batch_log.append("❌ Cannot resume: No batch handler or no remaining jobs")
                
        except Exception as e:
            error_msg = f"Error resuming batch submission: {str(e)}"
            print(error_msg)
            self.batch_log.append(f"⚠️ {error_msg}")
    
    def _restart_batch_with_remaining_jobs(self, remaining_jobs):
        """Restart batch processing with remaining jobs"""
        try:
            # Reset job index
            self.current_job_index = 0
            self.batch_jobs = remaining_jobs
            
            # Start new batch
            self.start_batch_submission()
            
        except Exception as e:
            error_msg = f"Error restarting batch: {str(e)}"
            print(error_msg)
            self.batch_log.append(f"⚠️ {error_msg}")

    ############### Latest Code 

    def export_job_plan(self):
        """Export the current job plan to Excel for review"""
        if not self.batch_jobs:
            QMessageBox.warning(self, "No Jobs", "No jobs have been prepared yet. Please select a protein and load ROI data first.")
            return
        
        try:
            # Get save path
            default_name = f"job_plan_{self.selected_protein['name']}_{len(self.batch_jobs)}_jobs.xlsx"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Job Plan",
                default_name,
                "Excel Files (*.xlsx);;All Files (*)"
            )
            
            if not file_path:
                return
            
            # Export job plan
            from protein_roi_loader import DataExporter
            DataExporter.export_job_plan(self.batch_jobs, file_path)
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Job plan exported successfully to:\n{file_path}\n\n"
                f"The file contains detailed information about all {len(self.batch_jobs)} planned jobs."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting job plan:\n{str(e)}")

    def validate_current_setup(self):
        """Validate the current protein and ROI setup before submission"""
        validation_messages = []
        
        # Check protein selection
        if not self.selected_protein:
            validation_messages.append("❌ No protein selected")
        else:
            validation_messages.append(f"✓ Protein: {self.selected_protein['name']} ({self.selected_protein['length']} AA)")
            if self.selected_protein.get('warnings'):
                validation_messages.append(f"  ⚠️ Warnings: {len(self.selected_protein['warnings'])}")
        
        # Check ROI data
        if not self.roi_data:
            validation_messages.append("❌ No ROI data loaded")
        else:
            validation_messages.append(f"✓ ROI sequences: {len(self.roi_data)}")
            valid_rois = [roi for roi in self.roi_data if roi.get('is_valid', True)]
            if len(valid_rois) != len(self.roi_data):
                validation_messages.append(f"  ⚠️ {len(self.roi_data) - len(valid_rois)} ROI sequences have warnings")
        
        # Check credentials
        has_email = self.alphafold_email.text().strip() != ""
        has_password = self.alphafold_password.text().strip() != ""
        
        if has_email and has_password:
            validation_messages.append("✓ AlphaFold credentials provided")
        else:
            validation_messages.append("❌ AlphaFold credentials missing")
        
        # Calculate job estimates
        if self.selected_protein and self.roi_data:
            total_jobs = len(self.roi_data)
            job_limit = self.job_limit_input.value()
            
            validation_messages.append(f"📊 Total jobs planned: {total_jobs}")
            validation_messages.append(f"📊 Daily job limit: {job_limit}")
            
            if total_jobs > job_limit:
                validation_messages.append(f"⚠️ Jobs exceed daily limit by {total_jobs - job_limit}")
            
            # Estimate processing time
            complexity_counts = {'Low': 0, 'Medium': 0, 'High': 0}
            if hasattr(self, 'batch_jobs') and self.batch_jobs:
                for job in self.batch_jobs:
                    complexity_counts[job.get('estimated_complexity', 'Medium')] += 1
            
            estimated_hours = (complexity_counts['Low'] * 0.5 + 
                            complexity_counts['Medium'] * 1.0 + 
                            complexity_counts['High'] * 2.0)
            validation_messages.append(f"⏱️ Estimated processing time: {estimated_hours:.1f} hours")
        
        # Show validation dialog
        validation_text = "\n".join(validation_messages)
        QMessageBox.information(self, "Setup Validation", validation_text)

    def export_protein_summary(self):
        """Export protein summary to Excel"""
        if not self.protein_data:
            QMessageBox.warning(self, "No Data", "No protein data to export.")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"protein_summary_{timestamp}.xlsx"
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Protein Summary",
                default_name,
                "Excel Files (*.xlsx);;All Files (*)"
            )
            
            if file_path:
                from protein_roi_loader import DataExporter
                DataExporter.export_protein_summary(self.protein_data, file_path)
                
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Protein summary exported to:\n{file_path}"
                )
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting protein summary:\n{str(e)}")

    
    def save_batch_log(self):
        """Save the batch log to a file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"alphafold_batch_log_{timestamp}.txt"
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Batch Log",
                default_name,
                "Text Files (*.txt);;All Files (*)"
            )
            
            if file_path:
                with open(file_path, 'w') as f:
                    f.write(f"AlphaFold Batch Processing Log\n")
                    f.write(f"Generated: {datetime.now().isoformat()}\n")
                    f.write("="*60 + "\n\n")
                    f.write(self.batch_log.toPlainText())
                
                QMessageBox.information(self, "Log Saved", f"Batch log saved to:\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving log file:\n{str(e)}")
    

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Log in Code~~~~~~~~~~~~~
    def check_existing_cookies(self):
        """Check if AlphaFold cookies already exist"""
        import os
        cookies_file = "alphafold_cookies.pkl"
        
        if os.path.exists(cookies_file):
            self.auto_login_button.setEnabled(True)
            self.login_status_label.setText("Status: Cookies found - ready for auto login")
            self.login_status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.batch_log.append("Found existing AlphaFold cookies")
        else:
            self.auto_login_button.setEnabled(False)
            self.login_status_label.setText("Status: Not logged in - manual login required")
            self.login_status_label.setStyleSheet("color: red; font-weight: bold;")

    def perform_manual_login(self):
        """Perform manual login to AlphaFold and save cookies"""
        try:
            from alphafold_login import AlphaFoldLogin
            
            # Create login handler
            self.alphafold_login_handler = AlphaFoldLogin()
            
            # Update UI
            self.manual_login_button.setEnabled(False)
            self.manual_login_button.setText("Opening browser...")
            self.login_status_label.setText("Status: Browser opened - complete login manually")
            self.login_status_label.setStyleSheet("color: blue; font-weight: bold;")
            
            self.batch_log.append("Starting manual login process...")
            self.batch_log.append("Browser will open - please complete Google login manually")
            
            # Start manual login process
            success = self.alphafold_login_handler.manual_login()
            
            if success:
                self.login_status_label.setText("Status: Successfully logged in and cookies saved")
                self.login_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.is_logged_in = True
                
                # Enable relevant buttons
                self.auto_login_button.setEnabled(True)
                self.validate_setup_button.setEnabled(True)
                self.update_batch_submit_button()
                
                self.batch_log.append("✓ Manual login successful - cookies saved")
                self.batch_log.append("You can now use 'Login with Saved Cookies' for future sessions")
                
                QMessageBox.information(
                    self,
                    "Login Successful",
                    "Successfully logged in to AlphaFold 3!\n\n"
                    "Your login cookies have been saved.\n"
                    "You can now proceed with batch job submission.\n\n"
                    "For future sessions, you can use 'Login with Saved Cookies'."
                )
                
            else:
                self.login_status_label.setText("Status: Manual login failed")
                self.login_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.batch_log.append("✗ Manual login failed")
                
                QMessageBox.warning(
                    self,
                    "Login Failed",
                    "Manual login to AlphaFold 3 failed.\n\n"
                    "Please check your internet connection and try again.\n"
                    "Make sure to complete the Google login process in the browser."
                )
                
        except Exception as e:
            self.login_status_label.setText("Status: Login error occurred")
            self.login_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.batch_log.append(f"✗ Login error: {str(e)}")
            
            QMessageBox.critical(
                self,
                "Login Error",
                f"An error occurred during login:\n\n{str(e)}\n\n"
                "Please try again or check the console for more details."
            )
            
        finally:
            # Reset button state
            self.manual_login_button.setEnabled(True)
            self.manual_login_button.setText("Manual Login & Save Cookies")

    def perform_auto_login(self):
        """Perform automatic login using saved cookies"""
        try:
            from alphafold_login import AlphaFoldLogin
            
            # Create login handler
            self.alphafold_login_handler = AlphaFoldLogin()
            
            # Update UI
            self.auto_login_button.setEnabled(False)
            self.auto_login_button.setText("Logging in...")
            self.login_status_label.setText("Status: Attempting auto login...")
            self.login_status_label.setStyleSheet("color: blue; font-weight: bold;")
            
            self.batch_log.append("Attempting automatic login with saved cookies...")
            
            # Attempt cookie-based login
            success = self.alphafold_login_handler.login_with_cookies()
            
            if success:
                self.login_status_label.setText("Status: Successfully logged in with cookies")
                self.login_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.is_logged_in = True
                
                # Enable relevant buttons
                self.validate_setup_button.setEnabled(True)
                self.update_batch_submit_button()
                
                self.batch_log.append("✓ Automatic login successful")
                
                QMessageBox.information(
                    self,
                    "Login Successful",
                    "Successfully logged in to AlphaFold 3 using saved cookies!\n\n"
                    "You can now proceed with batch job submission."
                )
                
            else:
                self.login_status_label.setText("Status: Auto login failed - cookies may be expired")
                self.login_status_label.setStyleSheet("color: orange; font-weight: bold;")
                self.batch_log.append("✗ Automatic login failed - cookies may be expired")
                
                # Ask user if they want to do manual login
                reply = QMessageBox.question(
                    self,
                    "Auto Login Failed",
                    "Automatic login failed. This usually means your saved cookies have expired.\n\n"
                    "Would you like to perform a manual login to refresh your cookies?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.perform_manual_login()
                    return
                
        except Exception as e:
            self.login_status_label.setText("Status: Auto login error occurred")
            self.login_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.batch_log.append(f"✗ Auto login error: {str(e)}")
            
            QMessageBox.critical(
                self,
                "Auto Login Error",
                f"An error occurred during automatic login:\n\n{str(e)}\n\n"
                "Try performing a manual login instead."
            )
            
        finally:
            # Reset button state
            self.auto_login_button.setEnabled(True)
            self.auto_login_button.setText("Login with Saved Cookies")

    def check_login_status(self):
        """Check current login status"""
        try:
            if not self.alphafold_login_handler:
                self.batch_log.append("No active login session")
                QMessageBox.information(self, "Login Status", "No active login session found.")
                return
            
            # Update UI
            self.check_login_button.setEnabled(False)
            self.check_login_button.setText("Checking...")
            self.batch_log.append("Checking login status...")
            
            # Here you could add additional checks by trying to access AlphaFold pages
            # For now, we'll just check if we have a login handler and cookies exist
            import os
            cookies_exist = os.path.exists("alphafold_cookies.pkl")
            
            if self.is_logged_in and cookies_exist:
                status_msg = "✓ Logged in with valid session"
                self.batch_log.append(status_msg)
                QMessageBox.information(self, "Login Status", "Currently logged in to AlphaFold 3.")
            else:
                status_msg = "✗ Not logged in or session expired"
                self.batch_log.append(status_msg)
                QMessageBox.warning(self, "Login Status", "Not currently logged in to AlphaFold 3.")
                
        except Exception as e:
            self.batch_log.append(f"Error checking login status: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error checking login status:\n{str(e)}")
            
        finally:
            # Reset button state
            self.check_login_button.setEnabled(True)
            self.check_login_button.setText("Check Login Status")

    # ~~~~~~~~~~~~~~~~~~~~~~~~ Download AlphaFold 3 Results ~~~~~~~~~~~~~~~~
    
    def browse_download_directory(self):
        """Browse for download directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory for AlphaFold Results",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if directory:
            self.download_directory = directory
            
            # Update UI
            self.download_dir_label.setText(directory)
            self.download_status_label.setText(f"Download folder: {directory}")
            self.download_status_label.setStyleSheet("color: green; font-size: 11px;")
            
            # Update batch submit button state
            self.update_batch_submit_button()
            
            # Log the change
            self.batch_log.append(f"Download directory set: {directory}")
            
            QMessageBox.information(
                self,
                "Download Directory Set",
                f"AlphaFold results will be downloaded to:\n{directory}"
            )
   
    def validate_download_configuration(self):
        """Validate that download configuration is properly set"""
        if not self.download_directory:
            return False, "Download directory not selected"
        
        if not os.path.exists(self.download_directory):
            return False, f"Download directory does not exist: {self.download_directory}"
        
        if not os.access(self.download_directory, os.W_OK):
            return False, f"No write permission for download directory: {self.download_directory}"
        
        return True, "Download configuration is valid"

    def get_download_configuration(self):
        """Get the current download configuration (UPDATED with screenshot setting)"""
        
        # Check if capture_screenshots checkbox exists and get its value
        capture_screenshots = False
        if hasattr(self, 'capture_screenshots') and self.capture_screenshots is not None:
            capture_screenshots = self.capture_screenshots.isChecked()
        
        return {
            'download_directory': self.download_directory,
            'job_timeout_minutes': self.job_timeout_input.value(),
            'status_check_interval_minutes': self.status_check_interval.value(),
            'auto_open_downloads': self.auto_open_downloads.isChecked(),
            'capture_screenshots': capture_screenshots  # Safe way to get the value
        }

    # Update your existing update_batch_submit_button method to include download check
    def update_batch_submit_button(self):
        """Updated the batch submit button state (modified to include download directory check)"""
        has_protein = self.selected_protein is not None
        has_roi = len(self.roi_data) > 0
        is_logged_in = self.is_logged_in
        has_download_dir = self.download_directory is not None  # NEW: Check download directory
        
        can_submit = has_protein and has_roi and is_logged_in and has_download_dir
        self.start_batch_button.setEnabled(can_submit)
        
        # Enable export button if we have protein and ROI data
        can_export = has_protein and has_roi
        self.export_plan_button.setEnabled(can_export)
        
        # Update job count and prepare batch jobs for export
        if has_protein and has_roi:
            try:
                selected_protein_index = self.protein_data.index(self.selected_protein)
                job_limit = self.job_limit_input.value()
                from protein_roi_loader import create_job_batch
                self.batch_jobs, _ = create_job_batch(
                    self.protein_data, 
                    self.roi_data, 
                    selected_protein_index, 
                    job_limit
                )
                total_jobs = len(self.batch_jobs)
                self.total_jobs_label.setText(f"Total jobs to submit: {total_jobs}")
            except Exception:
                self.total_jobs_label.setText("Total jobs to submit: 0")
        else:
            self.total_jobs_label.setText("Total jobs to submit: 0")
            self.batch_jobs = []
        
        # Update status message based on what's missing
        if not is_logged_in:
            self.batch_status_label.setText("Please login to AlphaFold 3 first")
        elif not has_protein:
            self.batch_status_label.setText("Please select a protein sequence")
        elif not has_roi:
            self.batch_status_label.setText("Please load ROI data")
        elif not has_download_dir:
            self.batch_status_label.setText("Please select download directory")
        else:
            self.batch_status_label.setText("Ready for batch submission")

    # Update your existing validate_current_setup method to include download validation
    def validate_current_setup(self):
        """Validate the current protein and ROI setup before submission"""
        validation_messages = []
        
        # Check protein selection
        if not self.selected_protein:
            validation_messages.append("❌ No protein selected")
        else:
            validation_messages.append(f"✓ Protein: {self.selected_protein['name']} ({self.selected_protein['length']} AA)")
            if self.selected_protein.get('warnings'):
                validation_messages.append(f"  ⚠️ Warnings: {len(self.selected_protein['warnings'])}")
        
        # Check ROI data
        if not self.roi_data:
            validation_messages.append("❌ No ROI data loaded")
        else:
            validation_messages.append(f"✓ ROI sequences: {len(self.roi_data)}")
            valid_rois = [roi for roi in self.roi_data if roi.get('is_valid', True)]
            if len(valid_rois) != len(self.roi_data):
                validation_messages.append(f"  ⚠️ {len(self.roi_data) - len(valid_rois)} ROI sequences have warnings")
        
        # Check login status
        if self.is_logged_in:
            validation_messages.append("✓ Logged in to AlphaFold 3")
        else:
            validation_messages.append("❌ Not logged in to AlphaFold 3")
        
        # Check download configuration (NEW)
        download_valid, download_msg = self.validate_download_configuration()
        if download_valid:
            validation_messages.append(f"✓ Download directory: {self.download_directory}")
            config = self.get_download_configuration()
            validation_messages.append(f"✓ Job timeout: {config['job_timeout_minutes']} minutes")
            validation_messages.append(f"✓ Status check interval: {config['status_check_interval_minutes']} minutes")
        else:
            validation_messages.append(f"❌ Download configuration: {download_msg}")
        
        # Calculate job estimates
        if self.selected_protein and self.roi_data:
            total_jobs = len(self.roi_data)
            job_limit = self.job_limit_input.value()
            
            validation_messages.append(f"📊 Total jobs planned: {total_jobs}")
            validation_messages.append(f"📊 Daily job limit: {job_limit}")
            
            if total_jobs > job_limit:
                validation_messages.append(f"⚠️ Jobs exceed daily limit by {total_jobs - job_limit}")
            
            # Estimate processing time
            estimated_hours = total_jobs * 0.5  # Rough estimate: 30 minutes per job
            validation_messages.append(f"⏱️ Estimated total processing time: {estimated_hours:.1f} hours")
        
        # Show validation dialog
        validation_text = "\n".join(validation_messages)
        QMessageBox.information(self, "Setup Validation", validation_text)    