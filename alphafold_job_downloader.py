"""
AlphaFold Job Downloader - UPDATED VERSION
Handles downloading of completed AlphaFold job results and taking screenshots of results pages
"""
import os
import time
import glob
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class AlphaFoldJobDownloader:
    """Downloads completed AlphaFold job results and captures screenshots"""
    
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
    
    def download_job_results(self, job_name, max_wait_minutes=5, take_screenshot=True):
        """Download results for a completed job and optionally take screenshot
        
        Args:
            job_name (str): Name of the job to download
            max_wait_minutes (int): Maximum time to wait for download
            take_screenshot (bool): Whether to take screenshot of results page
            
        Returns:
            dict: Download info with file path and screenshot path if successful, None if failed
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
            
            if not downloaded_file:
                print(f"Download failed or timed out for job: {job_name}")
                return None
            
            print(f"Successfully downloaded: {downloaded_file}")
            
            # Take screenshot of results page if requested
            screenshot_path = None
            if take_screenshot:
                screenshot_path = self._take_results_screenshot(job_name, job_row)
            
            return {
                'downloaded_file': downloaded_file,
                'screenshot_path': screenshot_path,
                'job_name': job_name
            }
                
        except Exception as e:
            print(f"Error downloading job results: {e}")
            return None
    
    def _take_results_screenshot(self, job_name, job_row):
        """Take screenshot of the results page for a job
        
        Args:
            job_name (str): Name of the job
            job_row: WebElement of the job row (to click options menu again)
            
        Returns:
            str: Path to screenshot file if successful, None if failed
        """
        try:
            print(f"Taking screenshot of results page for job: {job_name}")
            
            # Wait a moment for any previous actions to complete
            time.sleep(2)
            
            # Click the options menu again
            if not self._click_job_options_menu(job_row):
                print("Failed to open job options menu for screenshot")
                return None
            
            # Click the "Open results" option
            if not self._click_open_results_option():
                print("Failed to click 'Open results' option")
                return None
            
            # Wait for results page to load
            print("Waiting for results page to load...")
            time.sleep(5)  # Wait 5 seconds as requested
            
            # Take screenshot
            screenshot_filename = f"{job_name}_results_page.png"
            screenshot_path = os.path.join(self.download_directory, screenshot_filename)
            
            # Clean filename to be safe for file system
            safe_filename = self._clean_filename(screenshot_filename)
            screenshot_path = os.path.join(self.download_directory, safe_filename)
            
            self.driver.save_screenshot(screenshot_path)
            
            print(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            print(f"Error taking results screenshot: {e}")
            return None
    
    def _click_open_results_option(self):
        """Click the 'Open results' option from the dropdown menu
        
        Returns:
            bool: True if successful
        """
        try:
            # Wait for dropdown menu to appear and look for "Open results" link
            open_results_selectors = [
                "//a[@mat-menu-item]//span[contains(text(), 'Open results')]/..",
                "//a[@mat-menu-item and contains(@href, '/fold/')]",
                "//a[contains(@class, 'mat-mdc-menu-item')]//span[contains(text(), 'Open results')]/..",
                "//a[@mat-menu-item]//mat-icon[text()='check']/..",
                "/html/body/div[2]/div[2]/div/div/div/a[1]"  # Fallback to full XPath
            ]
            
            open_results_element = None
            for selector in open_results_selectors:
                try:
                    open_results_element = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"Found 'Open results' element using selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not open_results_element:
                # Try to find any menu item with "results" in the text
                menu_items = self.driver.find_elements(
                    By.XPATH, "//a[@mat-menu-item] | //button[@mat-menu-item]"
                )
                
                for item in menu_items:
                    item_text = item.text.lower()
                    if "results" in item_text or "open" in item_text:
                        open_results_element = item
                        print(f"Found potential 'Open results' item: {item_text}")
                        break
            
            if not open_results_element:
                print("Could not find 'Open results' option in menu")
                return False
            
            # Click the open results option
            self.driver.execute_script("arguments[0].click();", open_results_element)
            time.sleep(2)
            
            print("Successfully clicked 'Open results' option")
            return True
            
        except Exception as e:
            print(f"Error clicking 'Open results' option: {e}")
            return False
    
    def _clean_filename(self, filename):
        """Clean filename to be safe for file system
        
        Args:
            filename (str): Original filename
            
        Returns:
            str: Cleaned filename
        """
        import re
        # Remove or replace invalid characters
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove multiple underscores
        cleaned = re.sub(r'_+', '_', cleaned)
        return cleaned
    
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
            
            # Filter out temporary files and screenshots
            valid_files = [f for f in files if not f.endswith(('.crdownload', '.tmp', '.part', '.png'))]
            
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
    
    def download_all_completed_jobs(self, take_screenshots=True):
        """Download all completed jobs in the table
        
        Args:
            take_screenshots (bool): Whether to take screenshots of results pages
            
        Returns:
            list: List of download result dictionaries
        """
        try:
            download_results = []
            
            # Get all completed jobs
            completed_jobs = self._get_completed_jobs()
            
            for job_name in completed_jobs:
                print(f"Downloading results for: {job_name}")
                
                download_result = self.download_job_results(job_name, take_screenshot=take_screenshots)
                if download_result:
                    download_results.append(download_result)
                    print(f"Downloaded: {download_result['downloaded_file']}")
                    if download_result['screenshot_path']:
                        print(f"Screenshot: {download_result['screenshot_path']}")
                else:
                    print(f"Failed to download: {job_name}")
                
                # Small delay between downloads
                time.sleep(2)
            
            return download_results
            
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