"""
AlphaFold Job Monitor
Monitors job status until completion or failure
"""
import time
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class AlphaFoldJobMonitor:
    """Monitors AlphaFold job status"""
    
    def __init__(self, driver):
        """Initialize job monitor
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.wait = WebDriverWait(driver, 15)
        self.short_wait = WebDriverWait(driver, 5)
    
    def monitor_job_until_completion(self, job_name, timeout_minutes=120, 
                                   check_interval_minutes=5, progress_callback=None):
        """Monitor a job until it completes or times out
        
        Args:
            job_name (str): Name of the job to monitor
            timeout_minutes (int): Maximum time to wait in minutes
            check_interval_minutes (int): How often to check status in minutes
            progress_callback (callable): Function to call with progress updates
            
        Returns:
            str: Final job status ('completed', 'failed', 'timeout')
        """
        start_time = datetime.now()
        timeout_time = start_time + timedelta(minutes=timeout_minutes)
        check_count = 0
        
        if progress_callback:
            progress_callback(f"Starting monitoring for job: {job_name}")
        
        print(f"Monitoring job '{job_name}' with {timeout_minutes}min timeout")
        
        while datetime.now() < timeout_time:
            check_count += 1
            
            try:
                # Check job status
                status = self._check_job_status(job_name)
                
                elapsed_minutes = (datetime.now() - start_time).total_seconds() / 60
                
                if progress_callback:
                    progress_callback(f"Check #{check_count}: {status} (elapsed: {elapsed_minutes:.1f}min)")
                
                print(f"Job '{job_name}' status check #{check_count}: {status}")
                
                if status == "completed":
                    print(f"Job '{job_name}' completed successfully!")
                    if progress_callback:
                        progress_callback("Job completed successfully!")
                    return "completed"
                
                elif status == "failed":
                    print(f"Job '{job_name}' failed!")
                    if progress_callback:
                        progress_callback("Job failed!")
                    return "failed"
                
                elif status in ["running", "queued", "pending"]:
                    # Job is still processing, wait before next check
                    if progress_callback:
                        progress_callback(f"Job is {status}, waiting {check_interval_minutes} minutes...")
                    
                    print(f"Job '{job_name}' is {status}, waiting {check_interval_minutes} minutes...")
                    time.sleep(check_interval_minutes * 60)
                
                else:
                    # Unknown status, wait a bit and try again
                    if progress_callback:
                        progress_callback(f"Unknown status: {status}, retrying...")
                    
                    print(f"Unknown status '{status}' for job '{job_name}', waiting...")
                    time.sleep(60)  # Wait 1 minute for unknown status
            
            except Exception as e:
                print(f"Error checking job status: {e}")
                if progress_callback:
                    progress_callback(f"Error checking status: {str(e)}")
                
                # Wait a bit before retrying
                time.sleep(30)
        
        # Timeout reached
        print(f"Job '{job_name}' monitoring timed out after {timeout_minutes} minutes")
        if progress_callback:
            progress_callback(f"Monitoring timed out after {timeout_minutes} minutes")
        
        return "timeout"
    
    def _check_job_status(self, job_name):
        """Check the current status of a specific job
        
        Args:
            job_name (str): Name of the job to check
            
        Returns:
            str: Job status ('completed', 'failed', 'running', 'queued', 'unknown')
        """
        try:
            # Navigate to jobs page (jobs should appear at bottom of same page)
            print(f"Checking status for job: {job_name}")
            
            # Wait for jobs table to load (it appears after ~10 seconds)
            time.sleep(2)
            
            # Look for the jobs table
            jobs_table = None
            table_selectors = [
                "//table[@mat-table]",
                "//table[contains(@class, 'mat-mdc-table')]",
                "//table[contains(@class, 'cdk-table')]"
            ]
            
            for selector in table_selectors:
                try:
                    jobs_table = self.driver.find_element(By.XPATH, selector)
                    break
                except:
                    continue
            
            if not jobs_table:
                print("Jobs table not found, job may not have appeared yet")
                return "pending"
            
            # Look for the specific job by name
            job_row = self._find_job_row(job_name, jobs_table)
            
            if not job_row:
                print(f"Job '{job_name}' not found in jobs table yet")
                return "pending"
            
            # Extract status from the job row
            status = self._extract_job_status_from_row(job_row)
            print(f"Found job '{job_name}' with status: {status}")
            
            return status
            
        except Exception as e:
            print(f"Error checking job status: {e}")
            return "unknown"
    
    def _find_job_row(self, job_name, jobs_table):
        """Find the table row for a specific job
        
        Args:
            job_name (str): Name of the job to find
            jobs_table: WebElement of the jobs table
            
        Returns:
            WebElement: Job row if found, None otherwise
        """
        try:
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
            
            return None
            
        except Exception as e:
            print(f"Error finding job row: {e}")
            return None
    
    def _extract_job_status_from_row(self, job_row):
        """Extract job status from a table row
        
        Args:
            job_row: WebElement of the job row
            
        Returns:
            str: Job status
        """
        try:
            # Method 1: Look for status icon in the status column
            status_cell = job_row.find_element(
                By.XPATH, ".//td[contains(@class, 'mat-column-status')]"
            )
            
            # Look for status icon
            status_icons = status_cell.find_elements(By.XPATH, ".//mat-icon")
            
            for icon in status_icons:
                icon_text = icon.text.strip().lower()
                tooltip = icon.get_attribute("mattooltip")
                
                # Check icon text and tooltip for status indicators
                if icon_text == "check_circle" or (tooltip and "succeed" in tooltip.lower()):
                    return "completed"
                elif icon_text == "error" or (tooltip and "failed" in tooltip.lower()):
                    return "failed"
                elif icon_text == "schedule" or (tooltip and "running" in tooltip.lower()):
                    return "running"
                elif icon_text == "hourglass" or (tooltip and "queued" in tooltip.lower()):
                    return "queued"
            
            # Method 2: Look for text-based status indicators
            status_text = status_cell.text.lower()
            
            if "completed" in status_text or "success" in status_text:
                return "completed"
            elif "failed" in status_text or "error" in status_text:
                return "failed"
            elif "running" in status_text or "processing" in status_text:
                return "running"
            elif "queued" in status_text or "pending" in status_text:
                return "queued"
            
            # Method 3: Check for CSS classes that might indicate status
            status_classes = status_cell.get_attribute("class").lower()
            
            if "success" in status_classes or "completed" in status_classes:
                return "completed"
            elif "error" in status_classes or "failed" in status_classes:
                return "failed"
            elif "running" in status_classes or "processing" in status_classes:
                return "running"
            
            print(f"Could not determine status from row. Status cell text: '{status_cell.text}'")
            return "unknown"
            
        except Exception as e:
            print(f"Error extracting job status from row: {e}")
            return "unknown"
    
    def get_all_jobs_status(self):
        """Get status of all jobs in the table
        
        Returns:
            list: List of dictionaries with job information
        """
        try:
            jobs = []
            
            # Find jobs table
            jobs_table = self.driver.find_element(By.XPATH, "//table[@mat-table]")
            
            # Get all job rows
            job_rows = jobs_table.find_elements(
                By.XPATH, ".//tr[contains(@class, 'mat-mdc-row')]"
            )
            
            for row in job_rows:
                try:
                    # Extract job information
                    name_cell = row.find_element(
                        By.XPATH, ".//td[contains(@class, 'mat-column-name')]"
                    )
                    job_name = name_cell.text.strip()
                    
                    # Extract status
                    status = self._extract_job_status_from_row(row)
                    
                    # Extract date if available
                    try:
                        date_cell = row.find_element(
                            By.XPATH, ".//td[contains(@class, 'mat-column-date')]"
                        )
                        job_date = date_cell.text.strip()
                    except:
                        job_date = "Unknown"
                    
                    jobs.append({
                        'name': job_name,
                        'status': status,
                        'date': job_date
                    })
                    
                except Exception as e:
                    print(f"Error extracting job info from row: {e}")
                    continue
            
            return jobs
            
        except Exception as e:
            print(f"Error getting all jobs status: {e}")
            return []