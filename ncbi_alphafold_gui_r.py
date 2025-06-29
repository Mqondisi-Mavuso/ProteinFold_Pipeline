import sys
import os
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QRadioButton, QGroupBox, 
                             QTextEdit, QSpinBox, QMessageBox, QProgressBar, QButtonGroup,
                             QSplitter, QFileDialog, QTabWidget, QCheckBox, QComboBox,
                             QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from ncbi_threads import NCBISearchThread, SequenceDownloadThread
from ncbi_bulk_threads import BulkDownloadThread, ExcelLoadThread, RetryFailedThread
from preprocess_dna import SequenceProcessor
from alphafold_crawler_2 import AlphaFoldSubmitter
import pandas as pd
from pathlib import Path
from ncbi_bulk_threads import BulkPreprocessingThread

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
        
        # Store search results
        self.search_results = []
        self.selected_result_id = None
        self.current_fasta_path = None
        self.roi_sequence = None
        self.protein_sequence_text = None
        
        # Bulk download variables
        self.current_gene_list = []
        self.bulk_download_thread = None
        self.excel_load_thread = None
        self.retry_thread = None
        
        # Create the AlphaFold submitter
        self.alphafold_submitter = AlphaFoldSubmitter()
        
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
        
        # Create tabs for single and bulk download
        ncbi_tabs = QTabWidget()
        left_layout.addWidget(ncbi_tabs)
        
        # Tab 1: Single Sequence Download
        single_tab = self.create_single_download_tab()
        ncbi_tabs.addTab(single_tab, "Single Download")
        
        # Tab 2: Bulk Sequence Download
        bulk_tab = self.create_bulk_download_tab()
        ncbi_tabs.addTab(bulk_tab, "Bulk Download")
        
        # Right side - AlphaFold Predictor (unchanged)
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
        
        # Tab 1: Sequence Pre-processor (UPDATED WITH TABBED INTERFACE)
        preprocessor_tab = QWidget()
        preprocessor_layout = QVBoxLayout(preprocessor_tab)
        
        # Create a tab widget for single vs bulk preprocessing
        preprocess_tabs = QTabWidget()
        preprocessor_layout.addWidget(preprocess_tabs)
        
        # Single File Processing Tab (existing functionality)
        single_process_tab = QWidget()
        single_layout = QVBoxLayout(single_process_tab)
        
        # File loading section (existing)
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
        
        # Display loaded file path (existing)
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Current File:"))
        self.file_path_label = QLabel("No file loaded")
        path_layout.addWidget(self.file_path_label)
        path_layout.addStretch()
        file_layout.addLayout(path_layout)
        
        file_group.setLayout(file_layout)
        single_layout.addWidget(file_group)
        
        # ROI finder section (existing)
        roi_group = QGroupBox("Region of Interest (ROI) Finder")
        roi_layout = QVBoxLayout()
        
        # ROI input (existing)
        roi_input_layout = QHBoxLayout()
        roi_input_layout.addWidget(QLabel("ROI Pattern:"))
        self.roi_input = QLineEdit("CACCTG")  # Updated default ROI
        roi_input_layout.addWidget(self.roi_input)
        self.find_roi_button = QPushButton("Find ROI")
        self.find_roi_button.clicked.connect(self.find_roi)
        self.find_roi_button.setEnabled(False)
        roi_input_layout.addWidget(self.find_roi_button)
        roi_layout.addLayout(roi_input_layout)
        
        # ROI results (existing)
        roi_layout.addWidget(QLabel("Found ROI Sub-Sequence:"))
        self.roi_result = QTextEdit()
        self.roi_result.setReadOnly(True)
        self.roi_result.setMaximumHeight(100)
        roi_layout.addWidget(self.roi_result)
        
        roi_group.setLayout(roi_layout)
        single_layout.addWidget(roi_group)
        
        preprocess_tabs.addTab(single_process_tab, "Single File")
        
        # Bulk Processing Tab (NEW)
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
        
        # Process button
        self.process_directory_button = QPushButton("Process All FASTA Files")
        self.process_directory_button.clicked.connect(self.process_fasta_directory)
        self.process_directory_button.setEnabled(False)
        self.process_directory_button.setMinimumHeight(40)
        control_layout.addWidget(self.process_directory_button)
        
        # Progress bar
        self.preprocessing_progress = QProgressBar()
        control_layout.addWidget(self.preprocessing_progress)
        
        # Status label
        self.preprocessing_status = QLabel("Ready to process FASTA files")
        control_layout.addWidget(self.preprocessing_status)
        
        control_group.setLayout(control_layout)
        bulk_layout.addWidget(control_group)
        
        # Results display
        results_group = QGroupBox("Processing Results")
        results_layout = QVBoxLayout()
        
        # Summary info
        summary_layout = QHBoxLayout()
        self.files_processed_label = QLabel("Files processed: 0")
        self.roi_found_label = QLabel("ROI sequences found: 0")
        summary_layout.addWidget(self.files_processed_label)
        summary_layout.addWidget(self.roi_found_label)
        summary_layout.addStretch()
        results_layout.addLayout(summary_layout)
        
        # Results table preview
        results_layout.addWidget(QLabel("Summary Preview (first 10 rows):"))
        self.results_table = QTableWidget()
        self.results_table.setMaximumHeight(200)
        results_layout.addWidget(self.results_table)
        
        # Export button
        self.export_results_button = QPushButton("Export Full Results to Excel")
        self.export_results_button.clicked.connect(self.export_preprocessing_results)
        self.export_results_button.setEnabled(False)
        results_layout.addWidget(self.export_results_button)
        
        results_group.setLayout(results_layout)
        bulk_layout.addWidget(results_group)
        
        preprocess_tabs.addTab(bulk_process_tab, "Bulk Processing")
        
        # Add the remaining existing content (protein sequence section)
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
        
        # Tab 2: AlphaFold Submission
        submission_tab = QWidget()
        submission_layout = QVBoxLayout(submission_tab)
        
        # AlphaFold credentials
        creds_group = QGroupBox("AlphaFold 3 Credentials")
        creds_layout = QVBoxLayout()
        
        email_layout = QHBoxLayout()
        email_layout.addWidget(QLabel("Gmail Account:"))
        self.alphafold_email = QLineEdit()
        self.alphafold_email.textChanged.connect(self.update_submit_button)
        email_layout.addWidget(self.alphafold_email)
        creds_layout.addLayout(email_layout)
        
        password_layout = QHBoxLayout()
        password_layout.addWidget(QLabel("Password:"))
        self.alphafold_password = QLineEdit()
        self.alphafold_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.alphafold_password.textChanged.connect(self.update_submit_button)
        password_layout.addWidget(self.alphafold_password)
        creds_layout.addLayout(password_layout)
        
        save_creds = QCheckBox("Save credentials (stored locally)")
        creds_layout.addWidget(save_creds)
        
        creds_group.setLayout(creds_layout)
        submission_layout.addWidget(creds_group)
        
        # Submission settings
        settings_group = QGroupBox("Submission Settings")
        settings_layout = QVBoxLayout()
        
        # Job name
        job_name_layout = QHBoxLayout()
        job_name_layout.addWidget(QLabel("Job Name:"))
        self.job_name_input = QLineEdit("Protein-DNA Complex")
        job_name_layout.addWidget(self.job_name_input)
        settings_layout.addLayout(job_name_layout)
        
        # Job options
        self.multimer_model = QCheckBox("Use multimer model")
        settings_layout.addWidget(self.multimer_model)
        
        self.save_all_models = QCheckBox("Save all 5 models")
        settings_layout.addWidget(self.save_all_models)
        
        settings_group.setLayout(settings_layout)
        submission_layout.addWidget(settings_group)
        
        # Sequences review
        review_group = QGroupBox("Sequences for Submission")
        review_layout = QVBoxLayout()
        
        review_layout.addWidget(QLabel("DNA Sequence (ROI Sub-Sequence):"))
        self.dna_review = QTextEdit()
        self.dna_review.setReadOnly(True)
        self.dna_review.setMaximumHeight(80)
        review_layout.addWidget(self.dna_review)
        
        review_layout.addWidget(QLabel("Protein Sequence:"))
        self.protein_review = QTextEdit()
        self.protein_review.setReadOnly(True)
        self.protein_review.setMaximumHeight(80)
        review_layout.addWidget(self.protein_review)
        
        review_group.setLayout(review_layout)
        submission_layout.addWidget(review_group)
        
        # Submit button
        self.submit_button = QPushButton("Submit to AlphaFold 3")
        self.submit_button.clicked.connect(self.submit_to_alphafold)
        self.submit_button.setMinimumHeight(50)
        self.submit_button.setEnabled(False)
        submission_layout.addWidget(self.submit_button)
        
        # Add the submission tab
        tab_widget.addTab(submission_tab, "AlphaFold Submission")
        
        # Tab 3: Results Viewer
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
        
        # Add the results tab
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