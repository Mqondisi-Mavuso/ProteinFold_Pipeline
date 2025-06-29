import sys
import os
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QRadioButton, QGroupBox, 
                             QTextEdit, QSpinBox, QMessageBox, QProgressBar, QButtonGroup,
                             QSplitter, QFileDialog, QTabWidget, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from ncbi_threads import NCBISearchThread, SequenceDownloadThread
from preprocess_dna import SequenceProcessor
from alphafold_crawler_2 import AlphaFoldSubmitter

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NCBI Sequence Retriever & AlphaFold Submitter")
        self.setMinimumSize(1200, 700)
        
        # Store search results
        self.search_results = []
        self.selected_result_id = None
        self.current_fasta_path = None
        self.roi_sequence = None
        self.protein_sequence_text = None
        
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
        
        # Left side - NCBI Sequence Retriever
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # NCBI Retriever title
        ncbi_title = QLabel("NCBI Sequence Retriever")
        ncbi_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        left_layout.addWidget(ncbi_title)
        
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
        left_layout.addWidget(input_group)
        
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
        left_layout.addWidget(results_group)
        
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
        
        left_layout.addLayout(action_layout)
        
        # Status bar and progress
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        
        left_layout.addLayout(status_layout)
        
        # Right side - AlphaFold Predictor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # AlphaFold Predictor title
        af_title = QLabel("AlphaFold 3 Predictor")
        af_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        right_layout.addWidget(af_title)
        
        # Create tabs for the right side
        tab_widget = QTabWidget()
        right_layout.addWidget(tab_widget)
        
        # Tab 1: Sequence Pre-processor
        preprocessor_tab = QWidget()
        preprocessor_layout = QVBoxLayout(preprocessor_tab)
        
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
        preprocessor_layout.addWidget(file_group)
        
        # ROI finder section
        roi_group = QGroupBox("Region of Interest (ROI) Finder")
        roi_layout = QVBoxLayout()
        
        # ROI input
        roi_input_layout = QHBoxLayout()
        roi_input_layout.addWidget(QLabel("ROI Pattern:"))
        self.roi_input = QLineEdit("CACCTGA")  # Default ROI
        roi_input_layout.addWidget(self.roi_input)
        self.find_roi_button = QPushButton("Find ROI")
        self.find_roi_button.clicked.connect(self.find_roi)
        self.find_roi_button.setEnabled(False)
        roi_input_layout.addWidget(self.find_roi_button)
        roi_layout.addLayout(roi_input_layout)
        
        # ROI results
        roi_layout.addWidget(QLabel("Found ROI Sub-Sequence:"))
        self.roi_result = QTextEdit()
        self.roi_result.setReadOnly(True)
        self.roi_result.setMaximumHeight(100)
        roi_layout.addWidget(self.roi_result)
        
        roi_group.setLayout(roi_layout)
        preprocessor_layout.addWidget(roi_group)
        
        # Protein sequence section
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
        
        # Add widgets to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # Set initial sizes (50/50 split)
        splitter.setSizes([600, 600])
    
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