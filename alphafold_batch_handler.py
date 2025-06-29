"""
AlphaFold Batch Handler for processing multiple protein-DNA predictions
Handles job submission, monitoring, and result downloading
"""

import os
import time
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread

from alphafold_login import AlphaFoldLogin
from alphafold_upload import AlphaFoldUploader  
from alphafold_download import AlphaFoldDownloader


class AlphaFoldBatchHandler(QObject):
    """Handles batch processing of AlphaFold jobs"""
    
    # Signals for GUI communication
    job_submitted = pyqtSignal(dict, str)  # job_info, job_id
    job_completed = pyqtSignal(dict, str, str)  # job_info, job_id, results_path
    job_failed = pyqtSignal(dict, str)  # job_info, error_message
    batch_completed = pyqtSignal(dict)  # summary
    progress_update = pyqtSignal(str)  # status message
    job_limit_reached = pyqtSignal(str)  # warning message
    
    def __init__(self, email, password, output_dir="alphafold_batch_results"):
        super().__init__()
        self.email = email
        self.password = password
        self.output_dir = output_dir
        
        # Job tracking
        self.jobs_queue = []
        self.completed_jobs = []
        self.failed_jobs = []
        self.current_job = None
        self.is_running = False
        self.should_stop = False
        
        # AlphaFold components
        self.login_handler = None
        self.uploader = None
        self.downloader = None
        
        # Timing and limits
        self.job_submission_delay = 30  # seconds between submissions
        self.status_check_interval = 60  # seconds between status checks
        self.max_daily_jobs = 30
        self.jobs_submitted_today = 0
        
        # Results tracking
        self.results_summary = {
            'start_time': None,
            'end_time': None,
            'total_jobs': 0,
            'successful': 0,
            'failed': 0,
            'completed_jobs': [],
            'failed_jobs': [],
            'output_directory': output_dir
        }
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Timer for job monitoring
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_current_job_status)
    
    def start_batch(self, job_list, max_jobs=None):
        """Start batch processing of jobs
        
        Args:
            job_list (list): List of job dictionaries
            max_jobs (int, optional): Maximum number of jobs to submit
        """
        if self.is_running:
            self.progress_update.emit("Batch is already running!")
            return
        
        # Set job limit
        if max_jobs:
            self.max_daily_jobs = max_jobs
        
        # Prepare jobs
        self.jobs_queue = job_list.copy()
        self.completed_jobs = []
        self.failed_jobs = []
        self.jobs_submitted_today = 0
        
        # Update summary
        self.results_summary['start_time'] = datetime.now().isoformat()
        self.results_summary['total_jobs'] = len(self.jobs_queue)
        self.results_summary['successful'] = 0
        self.results_summary['failed'] = 0
        
        self.is_running = True
        self.should_stop = False
        
        self.progress_update.emit(f"Starting batch processing of {len(self.jobs_queue)} jobs")
        
        # Initialize AlphaFold login
        self._initialize_alphafold_connection()
        
        # Start processing
        self._process_next_job()
    
    def stop_batch(self):
        """Stop the batch processing"""
        self.should_stop = True
        self.is_running = False
        self.monitor_timer.stop()
        
        if self.login_handler:
            try:
                self.login_handler.cleanup()
            except:
                pass
        
        self.progress_update.emit("Batch processing stopped")
        self._finalize_batch()
    
    def _initialize_alphafold_connection(self):
        """Initialize connection to AlphaFold"""
        try:
            self.progress_update.emit("Initializing AlphaFold connection...")
            
            # Create login handler
            self.login_handler = AlphaFoldLogin()
            self.login_handler.setup(self.email, self.password)
            
            # Attempt login
            login_success = self.login_handler.login()
            
            if not login_success:
                self.progress_update.emit("Failed to login to AlphaFold. Please check credentials.")
                self._finalize_batch()
                return
            
            # Create uploader and downloader
            self.uploader = AlphaFoldUploader(self.login_handler.get_driver())
            self.downloader = AlphaFoldDownloader(self.login_handler.get_driver())
            
            self.progress_update.emit("AlphaFold connection established successfully")
            
        except Exception as e:
            self.progress_update.emit(f"Failed to initialize AlphaFold connection: {str(e)}")
            self._finalize_batch()
    
    def _process_next_job(self):
        """Process the next job in the queue"""
        if self.should_stop or not self.is_running:
            return
        
        # Check if we've reached the daily job limit
        if self.jobs_submitted_today >= self.max_daily_jobs:
            self.job_limit_reached.emit(
                f"Daily job limit of {self.max_daily_jobs} reached. "
                f"Completed {len(self.completed_jobs)} jobs successfully."
            )
            self._finalize_batch()
            return
        
        # Check if there are more jobs
        if not self.jobs_queue:
            self.progress_update.emit("All jobs completed!")
            self._finalize_batch()
            return
        
        # Get next job
        self.current_job = self.jobs_queue.pop(0)
        
        self.progress_update.emit(f"Submitting job: {self.current_job['job_name']}")
        
        # Submit the job
        self._submit_current_job()
    
    def _submit_current_job(self):
        """Submit the current job to AlphaFold"""
        try:
            # Configure uploader
            self.uploader.setup(
                job_name=self.current_job['job_name'],
                protein_sequence=self.current_job['protein_sequence'],
                dna_sequence=self.current_job['dna_sequence'],
                use_multimer=False,  # Set based on your needs
                save_all_models=True
            )
            
            # Submit job
            success = self.uploader.submit_job()
            
            if success:
                job_id = self.uploader.get_job_id()
                self.current_job['job_id'] = job_id
                self.current_job['submission_time'] = datetime.now().isoformat()
                self.current_job['status'] = 'Submitted'
                
                self.jobs_submitted_today += 1
                
                self.job_submitted.emit(self.current_job, job_id)
                self.progress_update.emit(f"Job submitted successfully: {job_id}")
                
                # Save job info
                self._save_job_info(self.current_job)
                
                # Start monitoring this job
                self._start_job_monitoring()
                
            else:
                error_msg = "Failed to submit job to AlphaFold"
                self.current_job['error'] = error_msg
                self.failed_jobs.append(self.current_job)
                self.job_failed.emit(self.current_job, error_msg)
                
                # Process next job after delay
                QTimer.singleShot(self.job_submission_delay * 1000, self._process_next_job)
                
        except Exception as e:
            error_msg = f"Error submitting job: {str(e)}"
            self.current_job['error'] = error_msg
            self.failed_jobs.append(self.current_job)
            self.job_failed.emit(self.current_job, error_msg)
            
            # Process next job after delay
            QTimer.singleShot(self.job_submission_delay * 1000, self._process_next_job)
    
    def _start_job_monitoring(self):
        """Start monitoring the current job status"""
        self.monitor_timer.start(self.status_check_interval * 1000)
    
    def check_current_job_status(self):
        """Check the status of the current job"""
        if not self.current_job or self.should_stop:
            return
        
        try:
            # Set job ID for downloader
            self.downloader.set_job_id(self.current_job['job_id'])
            
            # Check status
            status = self.downloader.check_job_status()
            
            self.current_job['status'] = status
            self.progress_update.emit(f"Job {self.current_job['job_id']} status: {status}")
            
            if status == "Completed":
                self.monitor_timer.stop()
                self._download_job_results()
                
            elif status == "Failed":
                self.monitor_timer.stop()
                error_msg = "AlphaFold job failed"
                self.current_job['error'] = error_msg
                self.failed_jobs.append(self.current_job)
                self.job_failed.emit(self.current_job, error_msg)
                
                # Process next job after delay
                QTimer.singleShot(self.job_submission_delay * 1000, self._process_next_job)
                
            # If status is "Running" or "Queued", continue monitoring
            
        except Exception as e:
            self.progress_update.emit(f"Error checking job status: {str(e)}")
    
    def _download_job_results(self):
        """Download results for the current completed job"""
        try:
            self.progress_update.emit(f"Downloading results for job: {self.current_job['job_id']}")
            
            # Create job-specific directory
            job_dir = os.path.join(self.output_dir, self.current_job['job_id'])
            os.makedirs(job_dir, exist_ok=True)
            
            # Download results
            success = self.downloader.download_results(job_dir)
            
            if success:
                self.current_job['results_path'] = job_dir
                self.current_job['download_time'] = datetime.now().isoformat()
                self.completed_jobs.append(self.current_job)
                
                # Extract and organize results
                self._organize_job_results(job_dir)
                
                self.job_completed.emit(
                    self.current_job, 
                    self.current_job['job_id'], 
                    job_dir
                )
                
                self.progress_update.emit(f"Results downloaded successfully to: {job_dir}")
                
            else:
                error_msg = "Failed to download job results"
                self.current_job['error'] = error_msg
                self.failed_jobs.append(self.current_job)
                self.job_failed.emit(self.current_job, error_msg)
            
            # Process next job after delay
            QTimer.singleShot(self.job_submission_delay * 1000, self._process_next_job)
            
        except Exception as e:
            error_msg = f"Error downloading results: {str(e)}"
            self.current_job['error'] = error_msg
            self.failed_jobs.append(self.current_job)
            self.job_failed.emit(self.current_job, error_msg)
            
            # Process next job after delay
            QTimer.singleShot(self.job_submission_delay * 1000, self._process_next_job)
    
    def _organize_job_results(self, job_dir):
        """Organize and extract job results"""
        try:
            # Look for zip files in the job directory
            zip_files = list(Path(job_dir).glob("*.zip"))
            
            for zip_file in zip_files:
                # Create extraction directory
                extract_dir = job_dir / "extracted"
                extract_dir.mkdir(exist_ok=True)
                
                # Extract zip file
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Create metadata file
                metadata = {
                    'job_info': self.current_job,
                    'extraction_time': datetime.now().isoformat(),
                    'extracted_files': [f.name for f in extract_dir.iterdir()]
                }
                
                metadata_file = job_dir / "job_metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                break  # Process only the first zip file
                
        except Exception as e:
            self.progress_update.emit(f"Warning: Could not organize results: {str(e)}")
    
    def _save_job_info(self, job_info):
        """Save job information to file"""
        try:
            jobs_dir = os.path.join(self.output_dir, "job_tracking")
            os.makedirs(jobs_dir, exist_ok=True)
            
            job_file = os.path.join(jobs_dir, f"job_{job_info['job_id']}.json")
            
            with open(job_file, 'w') as f:
                json.dump(job_info, f, indent=2)
                
        except Exception as e:
            self.progress_update.emit(f"Warning: Could not save job info: {str(e)}")
    
    def _finalize_batch(self):
        """Finalize the batch processing and generate summary"""
        self.is_running = False
        self.monitor_timer.stop()
        
        # Update summary
        self.results_summary['end_time'] = datetime.now().isoformat()
        self.results_summary['successful'] = len(self.completed_jobs)
        self.results_summary['failed'] = len(self.failed_jobs)
        self.results_summary['completed_jobs'] = self.completed_jobs
        self.results_summary['failed_jobs'] = self.failed_jobs
        
        # Save summary
        summary_file = os.path.join(self.output_dir, "batch_summary.json")
        try:
            with open(summary_file, 'w') as f:
                json.dump(self.results_summary, f, indent=2)
        except Exception as e:
            self.progress_update.emit(f"Warning: Could not save batch summary: {str(e)}")
        
        # Create CSV summary for easy viewing
        self._create_csv_summary()
        
        # Cleanup
        if self.login_handler:
            try:
                self.login_handler.cleanup()
            except:
                pass
        
        # Emit completion signal
        self.batch_completed.emit(self.results_summary)
    
    def _create_csv_summary(self):
        """Create a CSV summary of all jobs"""
        try:
            import pandas as pd
            
            # Prepare data for CSV
            all_jobs = self.completed_jobs + self.failed_jobs
            
            csv_data = []
            for job in all_jobs:
                csv_data.append({
                    'Job Name': job['job_name'],
                    'Protein Name': job['protein_name'],
                    'Gene Name': job['gene_name'],
                    'ROI Locus': job['roi_locus'],
                    'Job ID': job.get('job_id', 'N/A'),
                    'Status': job.get('status', 'Failed'),
                    'Submission Time': job.get('submission_time', 'N/A'),
                    'Download Time': job.get('download_time', 'N/A'),
                    'Results Path': job.get('results_path', 'N/A'),
                    'Error': job.get('error', 'N/A')
                })
            
            if csv_data:
                df = pd.DataFrame(csv_data)
                csv_file = os.path.join(self.output_dir, "batch_summary.csv")
                df.to_csv(csv_file, index=False)
                
        except Exception as e:
            self.progress_update.emit(f"Warning: Could not create CSV summary: {str(e)}")
    
    def get_batch_progress(self):
        """Get current batch progress information
        
        Returns:
            dict: Progress information
        """
        total_jobs = self.results_summary['total_jobs']
        completed = len(self.completed_jobs)
        failed = len(self.failed_jobs)
        remaining = len(self.jobs_queue)
        
        return {
            'total_jobs': total_jobs,
            'completed': completed,
            'failed': failed,
            'remaining': remaining,
            'progress_percent': int(((completed + failed) / max(1, total_jobs)) * 100),
            'jobs_submitted_today': self.jobs_submitted_today,
            'job_limit': self.max_daily_jobs
        }
    
    def pause_batch(self):
        """Pause the batch processing"""
        self.should_stop = True
        self.monitor_timer.stop()
        self.progress_update.emit("Batch processing paused")
    
    def resume_batch(self):
        """Resume the batch processing"""
        if not self.is_running:
            self.should_stop = False
            self.is_running = True
            
            if self.current_job and self.current_job.get('status') in ['Submitted', 'Running', 'Queued']:
                # Resume monitoring current job
                self._start_job_monitoring()
            else:
                # Process next job
                self._process_next_job()
            
            self.progress_update.emit("Batch processing resumed")


class BatchJobQueue:
    """Helper class for managing batch job queue and persistence"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.queue_file = os.path.join(output_dir, "job_queue.json")
    
    def save_queue(self, jobs_queue, completed_jobs, failed_jobs):
        """Save current queue state"""
        queue_data = {
            'timestamp': datetime.now().isoformat(),
            'jobs_queue': jobs_queue,
            'completed_jobs': completed_jobs,
            'failed_jobs': failed_jobs
        }
        
        try:
            with open(self.queue_file, 'w') as f:
                json.dump(queue_data, f, indent=2)
        except Exception as e:
            print(f"Error saving queue: {e}")
    
    def load_queue(self):
        """Load saved queue state"""
        try:
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    queue_data = json.load(f)
                return (
                    queue_data.get('jobs_queue', []),
                    queue_data.get('completed_jobs', []),
                    queue_data.get('failed_jobs', [])
                )
        except Exception as e:
            print(f"Error loading queue: {e}")
        
        return [], [], []
    
    def clear_queue(self):
        """Clear saved queue"""
        try:
            if os.path.exists(self.queue_file):
                os.remove(self.queue_file)
        except Exception as e:
            print(f"Error clearing queue: {e}")


def create_job_from_data(protein_data, roi_data):
    """Helper function to create a job dictionary from protein and ROI data
    
    Args:
        protein_data (dict): Protein information
        roi_data (dict): ROI information
        
    Returns:
        dict: Job dictionary ready for submission
    """
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
    
    job_name = f"Protein-DNA_{protein_data['name']}_{roi_data['gene_name']}_{roi_data['roi_locus']}_{timestamp}"
    
    return {
        'job_name': job_name,
        'protein_name': protein_data['name'],
        'protein_sequence': protein_data['sequence'],
        'dna_sequence': roi_data['roi_sequence'],
        'gene_name': roi_data['gene_name'],
        'roi_locus': roi_data['roi_locus'],
        'accession': roi_data.get('accession', 'Unknown'),
        'created_time': datetime.now().isoformat()
    }