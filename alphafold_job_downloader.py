"""
AlphaFold Job Downloader
Handles downloading of completed AlphaFold job results
"""
import os
import time
import glob
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class AlphaFoldJobDownloader:
    """Downloads completed AlphaFold job results"""
    
    def __init__(self, driver, download_directory):
        """Initialize job downloader
        
        Args:
            driver: Selenium WebDriver instance
            download_directory (str): Directory where files should be downloaded
        """
        self.driver = driver
        self.download_directory = os.path.abspath(download_directory)
        self.wait = WebDriverWait(driver, 15)
        self.short_wait = WebDriverWait(driver, 5)
        
        # Ensure download directory exists
        os.makedirs(self.download_directory, exist_ok=True)
    
    def download_job_results(self, job_name, max_wait_minutes=5):
        """Download results for a completed job
        
        Args:
            job_name (str): Name of the job to download
            max_wait_minutes (int): Maximum time to wait for download
            
        Returns:
            str: Path to downloaded file if successful, None if failed
        """
        try:
            print(f"Starting download for job: {job_name}")
            
            # Find the job in the table
            job_row = self._find_job_row(job_name)
            if not job_row:
                print(f"Could not find job '{job_name}' in results table")
                return None
            
            # Get current download count before clicking
            files_before = self._get_download_files_count()
            
            # Click the options menu for the job
            if not self._click_job_options_menu(job_row):
                print("Failed to open job options menu")
                return None
            
            # Click the download option
            if not self._click_download_option():
                print("Failed to click download option")
                return None
            
            # Wait for download to complete
            downloaded_file = self._wait_for_download_completion(
                files_before, 
                job_name, 
                max_wait_minutes
            )
            
            if downloaded_file:
                print(f"Successfully downloaded: {downloaded_file}")
                return downloaded_file
            else:
                print(f"Download failed or timed out for job: {job_name}")
                return None
                
        except Exception as e:
            print(f"Error downloading job results: {e}")
            return None
    
    def _find_job_row(self, job_name):
        """Find the table row for a specific job
        
        Args:
            job_name (str): Name of the job to find
            
        Returns:
            WebElement: Job row if found, None otherwise
        """
        try:
            # Look for jobs table
            jobs_table = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//table[@mat-table]"))
            )
            
            # Look for job name in table cells
            job_name_cells = jobs_table.find_elements(
                By.XPATH, 
                f".//td[contains(@class, 'mat-column-name') and contains(text(), '{job_name}')]"
            )
            
            if job_name_cells:
                # Return the parent row
                job_row = job_name_cells[0].find_element(By.XPATH, "./parent::tr")
                return job_row
            
            # Alternative: Look for partial matches
            all_name_cells = jobs_table.find_elements(
                By.XPATH, ".//td[contains(@class, 'mat-column-name')]"
            )
            
            for cell in all_name_cells:
                cell_text = cell.text.strip()
                if job_name in cell_text or cell_text in job_name:
                    job_row = cell.find_element(By.XPATH, "./parent::tr")
                    return job_row
            
            print(f"Job '{job_name}' not found in table")
            return None
            
        except Exception as e:
            print(f"Error finding job row: {e}")
            return None
    
    def _click_job_options_menu(self, job_row):
        """Click the options menu (more_vert) for a job row
        
        Args:
            job_row: WebElement of the job row
            
        Returns:
            bool: True if successful
        """
        try:
            # Look for options button in the row
            options_button = job_row.find_element(
                By.XPATH, 
                ".//button[contains(@class, 'fold-actions')]//mat-icon[text()='more_vert']/.."
            )
            
            # Scroll to button if needed
            self.driver.execute_script("arguments[0].scrollIntoView(true);", options_button)
            time.sleep(1)
            
            # Click the options button
            self.driver.execute_script("arguments[0].click();", options_button)
            time.sleep(1)
            
            print("Successfully clicked job options menu")
            return True
            
        except Exception as e:
            print(f"Error clicking job options menu: {e}")
            return False
    
    def _click_download_option(self):
        """Click the download option from the dropdown menu
        
        Returns:
            bool: True if successful
        """
        try:
            # Wait for dropdown menu to appear and look for download link
            download_selectors = [
                "//a[@mat-menu-item and @download]",
                "//a[contains(@class, 'mat-mdc-menu-item') and @download]",
                "//button[@mat-menu-item]//mat-icon[text()='download']/..",
                "//a[@mat-menu-item]//mat-icon[text()='download']/.."
            ]
            
            download_element = None
            for selector in download_selectors:
                try:
                    download_element = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not download_element:
                # Try to find any download-related menu item
                menu_items = self.driver.find_elements(
                    By.XPATH, "//button[@mat-menu-item] | //a[@mat-menu-item]"
                )
                
                for item in menu_items:
                    item_text = item.text.lower()
                    if "download" in item_text:
                        download_element = item
                        break
            
            if not download_element:
                print("Could not find download option in menu")
                return False
            
            # Click the download option
            self.driver.execute_script("arguments[0].click();", download_element)
            time.sleep(2)
            
            print("Successfully clicked download option")
            return True
            
        except Exception as e:
            print(f"Error clicking download option: {e}")
            return False
    
    def _get_download_files_count(self):
        """Get current number of files in download directory
        
        Returns:
            int: Number of files
        """
        try:
            files = glob.glob(os.path.join(self.download_directory, "*"))
            return len(files)
        except Exception as e:
            print(f"Error counting download files: {e}")
            return 0
    
    def _wait_for_download_completion(self, initial_file_count, job_name, max_wait_minutes):
        """Wait for download to complete
        
        Args:
            initial_file_count (int): Number of files before download
            job_name (str): Name of the job being downloaded
            max_wait_minutes (int): Maximum time to wait
            
        Returns:
            str: Path to downloaded file if successful, None if failed
        """
        try:
            print(f"Waiting for download to complete (max {max_wait_minutes} minutes)...")
            
            start_time = time.time()
            timeout_seconds = max_wait_minutes * 60
            
            while time.time() - start_time < timeout_seconds:
                # Check if new files appeared
                current_file_count = self._get_download_files_count()
                
                if current_file_count > initial_file_count:
                    # New file(s) appeared, find the most recent one
                    time.sleep(2)  # Wait a bit more to ensure download is complete
                    
                    recent_file = self._find_most_recent_download()
                    if recent_file:
                        # Check if it's related to our job
                        if self._is_job_related_file(recent_file, job_name):
                            return recent_file
                        else:
                            print(f"Found new file but doesn't match job: {recent_file}")
                
                # Check for .crdownload or .tmp files (indicating ongoing download)
                temp_files = glob.glob(os.path.join(self.download_directory, "*.crdownload"))
                temp_files.extend(glob.glob(os.path.join(self.download_directory, "*.tmp")))
                
                if temp_files:
                    print("Download in progress...")
                    time.sleep(5)
                    continue
                
                time.sleep(2)
            
            print(f"Download timeout reached ({max_wait_minutes} minutes)")
            return None
            
        except Exception as e:
            print(f"Error waiting for download completion: {e}")
            return None
    
    def _find_most_recent_download(self):
        """Find the most recently downloaded file
        
        Returns:
            str: Path to most recent file, None if no files found
        """
        try:
            files = glob.glob(os.path.join(self.download_directory, "*"))
            
            if not files:
                return None
            
            # Filter out temporary files
            valid_files = [f for f in files if not f.endswith(('.crdownload', '.tmp', '.part'))]
            
            if not valid_files:
                return None
            
            # Find most recent file
            most_recent = max(valid_files, key=os.path.getctime)
            return most_recent
            
        except Exception as e:
            print(f"Error finding most recent download: {e}")
            return None
    
    def _is_job_related_file(self, file_path, job_name):
        """Check if a downloaded file is related to the specified job
        
        Args:
            file_path (str): Path to the downloaded file
            job_name (str): Name of the job
            
        Returns:
            bool: True if file is related to the job
        """
        try:
            filename = os.path.basename(file_path)
            
            # Check if job name or parts of it are in the filename
            if job_name.lower() in filename.lower():
                return True
            
            # Check if it's a zip file (AlphaFold results are typically zipped)
            if filename.endswith('.zip'):
                # Check file creation time - if it's very recent, it's likely our file
                file_age_seconds = time.time() - os.path.getctime(file_path)
                if file_age_seconds < 60:  # Created within last minute
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error checking if file is job-related: {e}")
            return True  # Default to True if we can't determine
    
    def download_all_completed_jobs(self):
        """Download all completed jobs in the table
        
        Returns:
            list: List of downloaded file paths
        """
        try:
            downloaded_files = []
            
            # Get all completed jobs
            completed_jobs = self._get_completed_jobs()
            
            for job_name in completed_jobs:
                print(f"Downloading results for: {job_name}")
                
                downloaded_file = self.download_job_results(job_name)
                if downloaded_file:
                    downloaded_files.append(downloaded_file)
                    print(f"Downloaded: {downloaded_file}")
                else:
                    print(f"Failed to download: {job_name}")
                
                # Small delay between downloads
                time.sleep(2)
            
            return downloaded_files
            
        except Exception as e:
            print(f"Error downloading all completed jobs: {e}")
            return []
    
    def _get_completed_jobs(self):
        """Get list of completed job names
        
        Returns:
            list: List of completed job names
        """
        try:
            completed_jobs = []
            
            # Find jobs table
            jobs_table = self.driver.find_element(By.XPATH, "//table[@mat-table]")
            
            # Get all job rows
            job_rows = jobs_table.find_elements(
                By.XPATH, ".//tr[contains(@class, 'mat-mdc-row')]"
            )
            
            for row in job_rows:
                try:
                    # Check if job is completed
                    status_cell = row.find_element(
                        By.XPATH, ".//td[contains(@class, 'mat-column-status')]"
                    )
                    
                    # Look for completion indicators
                    completed_indicators = [
                        ".//mat-icon[text()='check_circle']",
                        ".//*[@mattooltip='Succeeded']",
                        ".//*[contains(text(), 'Completed')]"
                    ]
                    
                    is_completed = False
                    for indicator in completed_indicators:
                        if status_cell.find_elements(By.XPATH, indicator):
                            is_completed = True
                            break
                    
                    if is_completed:
                        # Get job name
                        name_cell = row.find_element(
                            By.XPATH, ".//td[contains(@class, 'mat-column-name')]"
                        )
                        job_name = name_cell.text.strip()
                        completed_jobs.append(job_name)
                        
                except Exception as e:
                    print(f"Error processing job row: {e}")
                    continue
            
            return completed_jobs
            
        except Exception as e:
            print(f"Error getting completed jobs: {e}")
            return []