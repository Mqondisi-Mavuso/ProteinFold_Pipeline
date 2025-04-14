import sys
import os
import traceback
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QRadioButton, QGroupBox, 
                             QTextEdit, QSpinBox, QMessageBox, QProgressBar, QButtonGroup)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from ncbi_sequence_fetcher import NCBISequenceFetcher

class NCBISearchThread(QThread):
    """Thread for handling NCBI searches without blocking the GUI"""
    result_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    
    def __init__(self, gene_name, organism, email):
        super().__init__()
        self.gene_name = gene_name
        self.organism = organism
        self.email = email
        
    def run(self):
        try:
            # Create fetcher and search
            fetcher = NCBISequenceFetcher(self.email)
            results = fetcher.search_gene(self.organism, self.gene_name)
            
            if not results:
                self.error_signal.emit(f"No results found for '{self.organism} {self.gene_name}'")
                return
            
            self.result_signal.emit(results)
            
        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)}\n{traceback.format_exc()}")


class SequenceDownloadThread(QThread):
    """Thread for downloading sequences without blocking the GUI"""
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str)  # New signal for progress updates
    
    def __init__(self, seq_id, seq_length, email, output_dir="."):
        super().__init__()
        self.seq_id = seq_id
        self.seq_length = seq_length
        self.email = email
        self.output_dir = output_dir
        
    def run(self):
        try:
            # Send progress update
            self.progress_signal.emit(f"Starting download of sequence ID: {self.seq_id}")
            
            # Create fetcher and download
            fetcher = NCBISequenceFetcher(self.email)
            
            # Make sure the output directory exists
            os.makedirs(self.output_dir, exist_ok=True)
            
            # Progress update
            self.progress_signal.emit("Sending request to NCBI...")
            
            # Download the sequence
            filepath = fetcher.download_sequence(self.seq_id, self.seq_length, self.output_dir)
            
            if not filepath:
                self.error_signal.emit("Failed to download sequence. Check console for details.")
                return
            
            # Verify the file exists and has content
            if not os.path.exists(filepath):
                self.error_signal.emit(f"File was not created at: {filepath}")
                return
                
            filesize = os.path.getsize(filepath)
            if filesize == 0:
                self.error_signal.emit(f"File was created but is empty: {filepath}")
                return
                
            self.progress_signal.emit(f"Successfully downloaded {filesize} bytes to {filepath}")
            self.finished_signal.emit(filepath)
            
        except Exception as e:
            traceback_str = traceback.format_exc()
            self.error_signal.emit(f"Error: {str(e)}\n{traceback_str}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NCBI Sequence Retriever & AlphaFold Submitter")
        self.setMinimumSize(700, 500)
        
        # Store search results
        self.search_results = []
        self.selected_result_id = None
        
        self.initUI()
        
    def initUI(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
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
        main_layout.addWidget(input_group)
        
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
        main_layout.addWidget(results_group)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.download_button = QPushButton("Download Selected")
        self.download_button.clicked.connect(self.download_sequence)
        self.download_button.setEnabled(False)
        action_layout.addWidget(self.download_button)
        
        self.alphafold_button = QPushButton("Submit to AlphaFold")
        self.alphafold_button.clicked.connect(self.submit_to_alphafold)
        self.alphafold_button.setEnabled(False)
        action_layout.addWidget(self.alphafold_button)
        
        main_layout.addLayout(action_layout)
        
        # Status bar and progress
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        
        main_layout.addLayout(status_layout)
    
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
        self.alphafold_button.setEnabled(False)
        
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
        
        # Enable AlphaFold button
        self.alphafold_button.setEnabled(True)
    
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
    
    def submit_to_alphafold(self):
        """Submit the sequence to AlphaFold (placeholder for now)"""
        QMessageBox.information(self, "AlphaFold Submission", 
                              "This feature will allow submission to AlphaFold 3.\n"
                              "Currently it's a placeholder for the next development phase.")


def download_gene_sequence(organism, gene_name, email, seq_length=2100):
    """Quick function to download a gene sequence without GUI
    
    This uses the same backend as the GUI but provides a simple function interface
    
    Returns:
        Path to the downloaded file or None if failed
    """
    try:
        # Create fetcher
        fetcher = NCBISequenceFetcher(email)
        
        # Find MANE select or RefSeq
        result = fetcher.find_mane_select(organism, gene_name)
        if not result:
            print(f"No results found for '{organism} {gene_name}'")
            return None
            
        # Download the sequence
        filepath = fetcher.download_sequence(result["id"], seq_length)
        return filepath
        
    except Exception as e:
        print(f"Error downloading sequence: {str(e)}")
        return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())