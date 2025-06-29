"""
AlphaFold results download module
This module handles checking job status and downloading results
"""
import os
import time
import json
import requests
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class AlphaFoldDownloader:
    """Class for checking job status and downloading results"""
    
    def __init__(self, driver=None):
        """Initialize the AlphaFold downloader
        
        Args:
            driver: Selenium WebDriver from login module
        """
        self.driver = driver
        self.job_id = None
        self.job_status = None
        self.screenshots_dir = "download_screenshots"
        
        # Create screenshots directory
        os.makedirs(self.screenshots_dir, exist_ok=True)
    
    def set_driver(self, driver):
        """Set the browser driver from login module
        
        Args:
            driver: Selenium WebDriver
        """
        self.driver = driver
    
    def set_job_id(self, job_id):
        """Set the job ID to check or download
        
        Args:
            job_id (str): AlphaFold job ID
        """
        self.job_id = job_id
    
    def take_screenshot(self, name):
        """Take a screenshot for debugging
        
        Args:
            name (str): Name for the screenshot
        """
        if self.driver:
            self.driver.save_screenshot(f"{self.screenshots_dir}/{name}.png")
            print(f"Screenshot saved: {name}.png")
    
    def load_job_info(self, job_id=None):
        """Load job information from a file
        
        Args:
            job_id (str, optional): Job ID to load. If None, loads most recent.
            
        Returns:
            bool: True if successful, False otherwise
        """
        # If job_id specified, use it. Otherwise, try to load most recent.
        if job_id:
            self.job_id = job_id
            
        # Check if we have a jobs directory
        if not os.path.exists("alphafold_jobs"):
            print("No alphafold_jobs directory found")
            return False
        
        try:
            if self.job_id:
                # Load specific job file
                job_file = os.path.join("alphafold_jobs", f"job_{self.job_id}.json")
                if not os.path.exists(job_file):
                    print(f"Job file not found: {job_file}")
                    return False
                    
                with open(job_file, 'r') as f:
                    job_info = json.load(f)
                print(f"Loaded job info for job ID: {self.job_id}")
            else:
                # Look for the most recent job file
                job_files = list(Path("alphafold_jobs").glob("job_*.json"))
                if not job_files:
                    print("No job files found in alphafold_jobs directory")
                    return False
                
                # Sort by modification time (most recent first)
                job_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                # Load the most recent job
                most_recent_job = str(job_files[0])
                print(f"Loading most recent job file: {most_recent_job}")
                
                with open(most_recent_job, 'r') as f:
                    job_info = json.load(f)
                
                # Get the job ID
                self.job_id = job_info.get("job_id")
                print(f"Loaded job info for job ID: {self.job_id}")
            
            # Populate the job status
            self.job_status = job_info.get("status")
            
            return True
        except Exception as e:
            print(f"Error loading job info: {e}")
            return False
    
    def check_job_status(self):
        """Check the status of a submitted job
        
        Returns:
            str: Job status (Queued, Running, Completed, Failed, Unknown)
        """
        if not self.driver:
            print("No browser driver provided. Please set a driver first.")
            return "Unknown"
            
        if not self.job_id:
            if not self.load_job_info():
                return "Unknown"
        
        try:
            # Navigate to job results page
            job_url = f"https://alphafoldserver.com/job/{self.job_id}"
            self.driver.get(job_url)
            print(f"Navigated to job results page: {self.job_id}")
            
            # Take a screenshot of the job status page
            self.take_screenshot("1_job_status")
            
            # Wait for page to load
            time.sleep(3)
            
            # Try to determine job status from page content
            page_source = self.driver.page_source.lower()
            
            if "completed" in page_source or "finished" in page_source or "done" in page_source:
                self.job_status = "Completed"
            elif "running" in page_source or "processing" in page_source or "in progress" in page_source:
                self.job_status = "Running"
            elif "queued" in page_source or "pending" in page_source or "waiting" in page_source:
                self.job_status = "Queued"
            elif "failed" in page_source or "error" in page_source:
                self.job_status = "Failed"
            else:
                self.job_status = "Unknown"
            
            # Update job status in the job info file
            self._update_job_status()
            
            print(f"Job status: {self.job_status}")
            return self.job_status
            
        except Exception as e:
            print(f"Error while checking job status: {e}")
            return "Unknown"
    
    def download_results(self, output_dir):
        """Download the results of a completed job
        
        Args:
            output_dir (str): Directory to save the results
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.driver:
            print("No browser driver provided. Please set a driver first.")
            return False
            
        if not self.job_id:
            if not self.load_job_info():
                return False
        
        try:
            # Check job status first
            status = self.check_job_status()
            
            if status != "Completed":
                print(f"Job is not completed (status: {status})")
                return False
            
            # Navigate to job results page (in case status check didn't do this)
            job_url = f"https://alphafoldserver.com/job/{self.job_id}"
            self.driver.get(job_url)
            print(f"Navigated to job results page for download: {self.job_id}")
            
            # Take a screenshot of the results page
            self.take_screenshot("2_results_page")
            
            # Wait for page to load
            time.sleep(3)
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            job_dir = os.path.join(output_dir, self.job_id)
            os.makedirs(job_dir, exist_ok=True)
            
            # Try to find and click the download button
            try:
                download_button = self.driver.find_element(By.XPATH, 
                    "//button[contains(text(), 'Download') or contains(@aria-label, 'download') or contains(@class, 'download')]")
                download_button.click()
                print("Clicked download button")
                
                # Wait for download dialog to appear
                time.sleep(2)
                self.take_screenshot("3_download_dialog")
                
                # Try to find and click the "Download all files" or similar option
                try:
                    download_all = self.driver.find_element(By.XPATH, 
                        "//button[contains(text(), 'Download all') or contains(text(), 'All files')]")
                    download_all.click()
                    print("Clicked 'Download all files'")
                except Exception as e:
                    print(f"Could not find 'Download all' button: {e}")
                    # Try individual download links
                    download_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'download') or contains(@download, '')]")
                    if download_links:
                        print(f"Found {len(download_links)} individual download links")
                        for i, link in enumerate(download_links):
                            try:
                                download_url = link.get_attribute("href")
                                # Use requests to download the file
                                self._download_file(download_url, job_dir)
                                print(f"Downloaded file {i+1} of {len(download_links)}")
                            except Exception as dl_err:
                                print(f"Error downloading file {i+1}: {dl_err}")
                    else:
                        print("No download links found")
                
                # Wait for downloads to complete
                print("Waiting for downloads to complete...")
                time.sleep(15)  # Adjust based on expected file size
                
                print(f"Results should be downloaded to your browser's download directory")
                print(f"Please move the files to: {job_dir}")
                
                # Update job status in the job info file
                self._update_job_status("Downloaded")
                
                return True
            except Exception as e:
                print(f"Error finding download button: {e}")
                return False
            
        except Exception as e:
            print(f"Error while downloading results: {e}")
            return False
    
    def _download_file(self, url, output_dir):
        """Download a file using requests
        
        Args:
            url (str): URL to download
            output_dir (str): Directory to save the file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get filename from URL
            filename = url.split('/')[-1]
            if '?' in filename:
                filename = filename.split('?')[0]
            
            # If no filename, use generic name
            if not filename:
                filename = f"download_{int(time.time())}.pdb"
            
            # Full path to save file
            filepath = os.path.join(output_dir, filename)
            
            # Download the file
            print(f"Downloading {url} to {filepath}")
            response = requests.get(url, stream=True)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                print(f"Downloaded {filepath}")
                return True
            else:
                print(f"Failed to download {url}: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"Error downloading file {url}: {e}")
            return False
    
    def _update_job_status(self, new_status=None):
        """Update job status in the job info file
        
        Args:
            new_status (str, optional): New status. If None, uses current status.
        """
        if not self.job_id:
            return
            
        job_file = os.path.join("alphafold_jobs", f"job_{self.job_id}.json")
        if not os.path.exists(job_file):
            return
        
        try:
            # Load existing job info
            with open(job_file, 'r') as f:
                job_info = json.load(f)
            
            # Update status
            if new_status:
                job_info["status"] = new_status
            else:
                job_info["status"] = self.job_status
            
            # Add last_checked timestamp
            job_info["last_checked"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Save updated job info
            with open(job_file, 'w') as f:
                json.dump(job_info, f, indent=2)
            
            print(f"Updated job status in {job_file}")
        except Exception as e:
            print(f"Error updating job status: {e}")
    
    def get_job_status(self):
        """Get the current job status
        
        Returns:
            str: Job status
        """
        return self.job_status

if __name__ == "__main__":
    # This module should be imported and used with a driver from the login module
    print("This module should be imported and used with a driver from the login module.")
    print("See alphafold_crawler.py for example usage.")