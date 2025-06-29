"""
Thread classes for NCBI operations to avoid blocking the GUI
"""
import traceback
from PyQt6.QtCore import QThread, pyqtSignal
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
    progress_signal = pyqtSignal(str)  # Signal for progress updates
    
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
            import os
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
