"""
Thread classes for NCBI bulk operations to avoid blocking the GUI
"""
import traceback
from PyQt6.QtCore import QThread, pyqtSignal
from ncbi_bulk_fetcher import NCBIBulkFetcher

class BulkDownloadThread(QThread):
    """Thread for handling bulk NCBI downloads without blocking the GUI"""
    progress_signal = pyqtSignal(int, int, str)  # current, total, message
    finished_signal = pyqtSignal(dict)  # summary dict
    error_signal = pyqtSignal(str)
    gene_completed_signal = pyqtSignal(str, bool, str)  # gene_name, success, message
    
    def __init__(self, email, gene_list, output_dir, seq_length=0, delay=1.0, max_retries=3):
        super().__init__()
        self.email = email
        self.gene_list = gene_list
        self.output_dir = output_dir
        self.seq_length = seq_length
        self.delay = delay
        self.max_retries = max_retries
        self.should_stop = False
        
    def stop(self):
        """Stop the bulk download process"""
        self.should_stop = True
        
    def run(self):
        try:
            # Create bulk fetcher
            bulk_fetcher = NCBIBulkFetcher(self.email)
            
            # Set up progress callback
            def progress_callback(current, total, message):
                if not self.should_stop:
                    self.progress_signal.emit(current, total, message)
            
            bulk_fetcher.set_progress_callback(progress_callback)
            
            # Start bulk download
            summary = bulk_fetcher.search_and_download_bulk(
                self.gene_list,
                self.output_dir,
                self.seq_length,
                self.delay,
                self.max_retries
            )
            
            if not self.should_stop:
                self.finished_signal.emit(summary)
            
        except Exception as e:
            error_msg = f"Bulk download error: {str(e)}\n{traceback.format_exc()}"
            self.error_signal.emit(error_msg)

class ExcelLoadThread(QThread):
    """Thread for loading gene lists from Excel files"""
    finished_signal = pyqtSignal(list)  # gene list
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str)  # status message
    
    def __init__(self, excel_path, gene_column=0, organism_column=None, 
                 status_column=None, sheet_name=None):
        super().__init__()
        self.excel_path = excel_path
        self.gene_column = gene_column
        self.organism_column = organism_column
        self.status_column = status_column
        self.sheet_name = sheet_name
        
    def run(self):
        try:
            self.progress_signal.emit("Loading Excel file...")
            
            # Create a temporary bulk fetcher just for loading
            temp_fetcher = NCBIBulkFetcher("temp@example.com")
            
            self.progress_signal.emit("Parsing gene list...")
            
            gene_list = temp_fetcher.load_gene_list_from_excel(
                self.excel_path,
                self.gene_column,
                self.organism_column,
                self.status_column,
                self.sheet_name
            )
            
            self.progress_signal.emit(f"Loaded {len(gene_list)} genes")
            self.finished_signal.emit(gene_list)
            
        except Exception as e:
            error_msg = f"Excel loading error: {str(e)}\n{traceback.format_exc()}"
            self.error_signal.emit(error_msg)

class RetryFailedThread(QThread):
    """Thread for retrying failed downloads"""
    progress_signal = pyqtSignal(int, int, str)  # current, total, message
    finished_signal = pyqtSignal(dict)  # updated summary dict
    error_signal = pyqtSignal(str)
    
    def __init__(self, email, summary_file, output_dir, max_retries=3):
        super().__init__()
        self.email = email
        self.summary_file = summary_file
        self.output_dir = output_dir
        self.max_retries = max_retries
        self.should_stop = False
        
    def stop(self):
        """Stop the retry process"""
        self.should_stop = True
        
    def run(self):
        try:
            # Create bulk fetcher
            bulk_fetcher = NCBIBulkFetcher(self.email)
            
            # Set up progress callback
            def progress_callback(current, total, message):
                if not self.should_stop:
                    self.progress_signal.emit(current, total, message)
            
            bulk_fetcher.set_progress_callback(progress_callback)
            
            # Retry failed downloads
            updated_summary = bulk_fetcher.retry_failed_downloads(
                self.summary_file,
                self.output_dir,
                self.max_retries
            )
            
            if not self.should_stop:
                self.finished_signal.emit(updated_summary)
            
        except Exception as e:
            error_msg = f"Retry error: {str(e)}\n{traceback.format_exc()}"
            self.error_signal.emit(error_msg)
