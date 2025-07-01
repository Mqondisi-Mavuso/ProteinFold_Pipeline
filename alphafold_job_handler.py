"""
AlphaFold Job Handler
Main orchestrator for AlphaFold job submission, monitoring, and downloading
"""
import os
import time
import json
from datetime import datetime, timedelta
from PyQt6.QtCore import QThread, pyqtSignal

from alphafold_job_submitter import AlphaFoldJobSubmitter
from alphafold_job_monitor import AlphaFoldJobMonitor
from alphafold_job_downloader import AlphaFoldJobDownloader
from alphafold_browser_manager import AlphaFoldBrowserManager


class AlphaFoldJobHandler(QThread):
    """Main handler for AlphaFold job processing"""
    
    # Signals for GUI updates
    progress_update = pyqtSignal(str)  # status message
    job_started = pyqtSignal(str, str)  # job_name, job_id
    job_completed = pyqtSignal(str, str, str)  # job_name, job_id, download_path
    job_failed = pyqtSignal(str, str)  # job_name, error_message
    batch_completed = pyqtSignal(dict)  # summary statistics
    job_progress = pyqtSignal(int, int, str)  # current_job, total_jobs, current_status
    
    def __init__(self, login_handler, download_config):
        """Initialize the job handler
        
        Args:
            login_handler: AlphaFoldLogin instance with active session
            download_config: Dictionary with download configuration
        """
        super().__init__()
        
        self.login_handler = login_handler
        self.download_config = download_config
        self.jobs_to_process = []
        self.current_job_index = 0
        self.should_stop = False
        
        # Results tracking
        self.successful_jobs = []
        self.failed_jobs = []
        self.processing_log = []
        
        # Components
        self.browser_manager = None
        self.job_submitter = None
        self.job_monitor = None
        self.job_downloader = None
        
        # Create results directory
        self.results_dir = self._create_results_directory()
    
    def _create_results_directory(self):
        """Create timestamped results directory"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_dir = os.path.join(
            self.download_config['download_directory'],
            f"alphafold_batch_{timestamp}"
        )
        os.makedirs(results_dir, exist_ok=True)
        return results_dir
    
    def setup_components(self):
        """Initialize all components with the browser session"""
        try:
            # Set up browser manager with download configuration
            self.browser_manager = AlphaFoldBrowserManager(
                self.login_handler,
                self.download_config['download_directory']
            )
            
            if not self.browser_manager.setup_browser():
                raise Exception("Failed to setup browser with download settings")
            
            # Initialize components with the configured browser
            driver = self.browser_manager.get_driver()
            
            self.job_submitter = AlphaFoldJobSubmitter(driver)
            self.job_monitor = AlphaFoldJobMonitor(driver)
            self.job_downloader = AlphaFoldJobDownloader(
                driver, 
                self.download_config['download_directory']
            )
            
            self.progress_update.emit("✓ Browser and components initialized successfully")
            return True
            
        except Exception as e:
            self.progress_update.emit(f"✗ Failed to setup components: {str(e)}")
            return False
    
    def set_jobs(self, jobs_list):
        """Set the list of jobs to process
        
        Args:
            jobs_list: List of job dictionaries with protein/DNA sequences
        """
        self.jobs_to_process = jobs_list
        self.current_job_index = 0
        
        # Log job queue
        self.progress_update.emit(f"Job queue initialized with {len(jobs_list)} jobs")
        self._log_event("job_queue_initialized", {
            "total_jobs": len(jobs_list),
            "timestamp": datetime.now().isoformat()
        })
    
    def stop_processing(self):
        """Stop the job processing"""
        self.should_stop = True
        self.progress_update.emit("Stopping job processing...")
    
    def run(self):
        """Main processing loop"""
        try:
            self.progress_update.emit("Starting AlphaFold batch processing...")
            
            # Setup components
            if not self.setup_components():
                return
            
            # Process each job sequentially
            for i, job in enumerate(self.jobs_to_process):
                if self.should_stop:
                    self.progress_update.emit("Processing stopped by user")
                    break
                
                self.current_job_index = i
                job_name = job['job_name']
                
                # Update progress
                self.job_progress.emit(i + 1, len(self.jobs_to_process), f"Processing {job_name}")
                
                try:
                    # Process single job
                    success = self._process_single_job(job)
                    
                    if success:
                        self.successful_jobs.append(job)
                        self.progress_update.emit(f"✓ Job {job_name} completed successfully")
                    else:
                        self.failed_jobs.append({
                            'job': job,
                            'error': 'Processing failed',
                            'timestamp': datetime.now().isoformat()
                        })
                        self.job_failed.emit(job_name, "Processing failed")
                        self.progress_update.emit(f"✗ Job {job_name} failed")
                    
                except Exception as e:
                    error_msg = f"Error processing job {job_name}: {str(e)}"
                    self.failed_jobs.append({
                        'job': job,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
                    self.job_failed.emit(job_name, str(e))
                    self.progress_update.emit(f"✗ {error_msg}")
                
                # Small delay between jobs
                if i < len(self.jobs_to_process) - 1:  # Not the last job
                    time.sleep(2)
            
            # Generate final summary
            self._generate_batch_summary()
            
        except Exception as e:
            self.progress_update.emit(f"Critical error in batch processing: {str(e)}")
        finally:
            self._cleanup()
    
    def _process_single_job(self, job):
        """Process a single job from submission to download
        
        Args:
            job: Job dictionary with sequences and metadata
            
        Returns:
            bool: True if successful, False otherwise
        """
        job_name = job['job_name']
        
        try:
            # Step 1: Submit job
            self.progress_update.emit(f"Submitting job: {job_name}")
            job_id = self.job_submitter.submit_job(
                protein_sequence=job['protein_sequence'],
                dna_sequence=job['dna_sequence'],
                job_name=job_name
            )
            
            if not job_id:
                self.progress_update.emit(f"Failed to submit job: {job_name}")
                return False
            
            self.job_started.emit(job_name, job_id)
            self.progress_update.emit(f"Job submitted with ID: {job_id}")
            
            # Step 2: Monitor job until completion
            self.progress_update.emit(f"Monitoring job: {job_name}")
            timeout_minutes = self.download_config['job_timeout_minutes']
            check_interval = self.download_config['status_check_interval_minutes']
            
            final_status = self.job_monitor.monitor_job_until_completion(
                job_name=job_name,
                timeout_minutes=timeout_minutes,
                check_interval_minutes=check_interval,
                progress_callback=lambda msg: self.progress_update.emit(f"{job_name}: {msg}")
            )
            
            if final_status != "completed":
                self.progress_update.emit(f"Job {job_name} did not complete successfully: {final_status}")
                return False
            
            # Step 3: Download results
            self.progress_update.emit(f"Downloading results for: {job_name}")
            download_path = self.job_downloader.download_job_results(job_name)
            
            if download_path:
                self.job_completed.emit(job_name, job_id, download_path)
                self.progress_update.emit(f"Results downloaded to: {download_path}")
                return True
            else:
                self.progress_update.emit(f"Failed to download results for: {job_name}")
                return False
        
        except Exception as e:
            self.progress_update.emit(f"Error in job processing: {str(e)}")
            return False
    
    def _log_event(self, event_type, data):
        """Log processing events"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'data': data
        }
        self.processing_log.append(log_entry)
    
    def _generate_batch_summary(self):
        """Generate and save batch processing summary"""
        summary = {
            'batch_info': {
                'start_time': self.processing_log[0]['timestamp'] if self.processing_log else None,
                'end_time': datetime.now().isoformat(),
                'total_jobs': len(self.jobs_to_process),
                'successful_jobs': len(self.successful_jobs),
                'failed_jobs': len(self.failed_jobs),
                'success_rate': len(self.successful_jobs) / len(self.jobs_to_process) * 100 if self.jobs_to_process else 0
            },
            'download_config': self.download_config,
            'results_directory': self.results_dir,
            'successful_jobs': self.successful_jobs,
            'failed_jobs': self.failed_jobs,
            'processing_log': self.processing_log
        }
        
        # Save summary to file
        summary_file = os.path.join(self.results_dir, "batch_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Save failed jobs separately for review
        if self.failed_jobs:
            failed_jobs_file = os.path.join(self.results_dir, "failed_jobs.json")
            with open(failed_jobs_file, 'w') as f:
                json.dump(self.failed_jobs, f, indent=2)
        
        self.progress_update.emit(f"Batch summary saved to: {summary_file}")
        self.batch_completed.emit(summary['batch_info'])
    
    def _cleanup(self):
        """Clean up resources"""
        try:
            if self.browser_manager:
                self.browser_manager.cleanup()
            self.progress_update.emit("Cleanup completed")
        except Exception as e:
            self.progress_update.emit(f"Error during cleanup: {str(e)}")
    
    def get_processing_summary(self):
        """Get current processing summary"""
        return {
            'total_jobs': len(self.jobs_to_process),
            'processed_jobs': self.current_job_index,
            'successful_jobs': len(self.successful_jobs),
            'failed_jobs': len(self.failed_jobs),
            'remaining_jobs': len(self.jobs_to_process) - self.current_job_index - 1
        }