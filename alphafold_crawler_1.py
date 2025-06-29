"""
AlphaFold 3 submission and results retrieval module using Selenium and BeautifulSoup
"""
import os
import time
import json
import requests
import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

class AlphaFoldSubmitter:
    """Class for submitting jobs to AlphaFold 3 and retrieving results"""
    
    def __init__(self):
        """Initialize the AlphaFold submitter"""
        self.driver = None
        self.email = None
        self.password = None
        self.job_name = None
        self.dna_sequence = None
        self.protein_sequence = None
        self.use_multimer = False
        self.save_all_models = False
        self.job_id = None
        self.job_status = None
        self.results_url = None
    
    def setup(self, email, password, job_name, dna_sequence, protein_sequence, 
              use_multimer=False, save_all_models=False):
        """Set up the AlphaFold submitter with credentials and sequences
        
        Args:
            email (str): Gmail email address
            password (str): Gmail password
            job_name (str): Name for the AlphaFold job
            dna_sequence (str): DNA sequence
            protein_sequence (str): Protein sequence
            use_multimer (bool): Whether to use the multimer model
            save_all_models (bool): Whether to save all 5 models
        """
        self.email = email
        self.password = password
        self.job_name = job_name
        self.dna_sequence = dna_sequence
        self.protein_sequence = protein_sequence
        self.use_multimer = use_multimer
        self.save_all_models = save_all_models
    
    def init_browser(self):
        """Initialize the browser for Selenium"""
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Initialize the driver
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_window_size(1920, 1080)
    
    def login_to_alphafold(self):
        """Login to AlphaFold 3 with Google account"""
        try:
            # Navigate to AlphaFold 3
            self.driver.get("https://alphafold.ebi.ac.uk/")
            
            # Wait for the page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.LINK_TEXT, "Sign in"))
            )
            
            # Click on sign in
            self.driver.find_element(By.LINK_TEXT, "Sign in").click()
            
            # Wait for Google sign-in page
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "identifierId"))
            )
            
            # Enter email
            email_field = self.driver.find_element(By.ID, "identifierId")
            email_field.send_keys(self.email)
            email_field.send_keys(Keys.RETURN)
            
            # Wait for password field
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            
            # Enter password
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.send_keys(self.password)
            password_field.send_keys(Keys.RETURN)
            
            # Wait for successful login
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.LINK_TEXT, "Submit"))
            )
            
            print("Successfully logged in to AlphaFold 3")
            return True
            
        except TimeoutException as e:
            print(f"Timeout during login: {e}")
            return False
        except Exception as e:
            print(f"Error during login: {e}")
            return False
    
    def submit_job(self):
        """Submit a new job to AlphaFold 3"""
        try:
            # Initialize browser if not already done
            if self.driver is None:
                self.init_browser()
            
            # Login if not already logged in
            self.login_to_alphafold()
            
            # Navigate to submission page
            self.driver.find_element(By.LINK_TEXT, "Submit").click()
            
            # Wait for submission form
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "jobName"))
            )
            
            # Fill out the form
            # Job name
            job_name_field = self.driver.find_element(By.ID, "jobName")
            job_name_field.clear()
            job_name_field.send_keys(self.job_name)
            
            # Select protein-DNA complex
            complex_type = self.driver.find_element(By.ID, "complex-type-dna")
            complex_type.click()
            
            # Enter protein sequence
            protein_field = self.driver.find_element(By.ID, "proteinSequence")
            protein_field.clear()
            protein_field.send_keys(self.protein_sequence)
            
            # Enter DNA sequence
            dna_field = self.driver.find_element(By.ID, "dnaSequence")
            dna_field.clear()
            dna_field.send_keys(self.dna_sequence)
            
            # Select multimer model if requested
            if self.use_multimer:
                multimer_option = self.driver.find_element(By.ID, "multimer-model")
                multimer_option.click()
            
            # Save all models if requested
            if self.save_all_models:
                all_models_option = self.driver.find_element(By.ID, "save-all-models")
                all_models_option.click()
            
            # Submit the job
            submit_button = self.driver.find_element(By.ID, "submit-job")
            submit_button.click()
            
            # Wait for confirmation
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, "job-submitted"))
            )
            
            # Get the job ID from the confirmation page
            job_info = self.driver.find_element(By.CLASS_NAME, "job-info").text
            self.job_id = job_info.split("Job ID:")[1].strip().split()[0]
            
            # Store the results URL
            self.results_url = f"https://alphafold.ebi.ac.uk/job/{self.job_id}"
            
            print(f"Successfully submitted job with ID: {self.job_id}")
            self.job_status = "Submitted"
            
            # Save job info to a file for later reference
            self._save_job_info()
            
            return True
            
        except TimeoutException as e:
            print(f"Timeout during job submission: {e}")
            return False
        except Exception as e:
            print(f"Error during job submission: {e}")
            return False
        finally:
            # Close the browser
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def check_job_status(self):
        """Check the status of a submitted job
        
        Returns:
            str: Job status (Queued, Running, Completed, Failed, Unknown)
        """
        # If we don't have a job ID, try to load from saved info
        if not self.job_id:
            self._load_job_info()
            
            # If still no job ID, return unknown
            if not self.job_id:
                return "Unknown"
        
        try:
            # Initialize browser if not already done
            if self.driver is None:
                self.init_browser()
            
            # Login if not already logged in
            self.login_to_alphafold()
            
            # Navigate to job results page
            self.driver.get(f"https://alphafold.ebi.ac.uk/job/{self.job_id}")
            
            # Wait for status element
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "job-status"))
            )
            
            # Get the status
            status_element = self.driver.find_element(By.CLASS_NAME, "job-status")
            status_text = status_element.text.strip()
            
            # Parse the status
            if "Completed" in status_text:
                self.job_status = "Completed"
            elif "Running" in status_text:
                self.job_status = "Running"
            elif "Queued" in status_text:
                self.job_status = "Queued"
            elif "Failed" in status_text:
                self.job_status = "Failed"
            else:
                self.job_status = "Unknown"
            
            print(f"Job status: {self.job_status}")
            return self.job_status
            
        except TimeoutException as e:
            print(f"Timeout while checking job status: {e}")
            return "Unknown"
        except Exception as e:
            print(f"Error while checking job status: {e}")
            return "Unknown"
        finally:
            # Close the browser
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def download_results(self, output_dir):
        """Download the results of a completed job
        
        Args:
            output_dir (str): Directory to save the results
            
        Returns:
            bool: True if successful, False otherwise
        """
        # If we don't have a job ID, try to load from saved info
        if not self.job_id:
            self._load_job_info()
            
            # If still no job ID, return false
            if not self.job_id:
                print("No job ID found")
                return False
        
        try:
            # Check job status first
            status = self.check_job_status()
            
            if status != "Completed":
                print(f"Job is not completed (status: {status})")
                return False
            
            # Initialize browser if not already done
            if self.driver is None:
                self.init_browser()
            
            # Login if not already logged in
            self.login_to_alphafold()
            
            # Navigate to job results page
            self.driver.get(f"https://alphafold.ebi.ac.uk/job/{self.job_id}")
            
            # Wait for download links
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.LINK_TEXT, "Download results"))
            )
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            job_dir = os.path.join(output_dir, self.job_id)
            os.makedirs(job_dir, exist_ok=True)
            
            # Download the result files
            download_link = self.driver.find_element(By.LINK_TEXT, "Download results")
            download_url = download_link.get_attribute("href")
            
            # Use requests to download the file
            response = requests.get(download_url, stream=True)
            if response.status_code == 200:
                zip_path = os.path.join(job_dir, f"{self.job_id}_results.zip")
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                print(f"Results downloaded to {zip_path}")
                
                # Also save the results page HTML for reference
                page_html = self.driver.page_source
                html_path = os.path.join(job_dir, f"{self.job_id}_results.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page_html)
                
                return True
            else:
                print(f"Failed to download results: HTTP {response.status_code}")
                return False
            
        except TimeoutException as e:
            print(f"Timeout while downloading results: {e}")
            return False
        except Exception as e:
            print(f"Error while downloading results: {e}")
            return False
        finally:
            # Close the browser
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def _save_job_info(self):
        """Save job information to a file for later reference"""
        job_info = {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "email": self.email,
            "results_url": self.results_url,
            "submission_time": datetime.datetime.now().isoformat(),
            "status": self.job_status,
            "dna_sequence": self.dna_sequence,
            "protein_sequence": self.protein_sequence,
            "use_multimer": self.use_multimer,
            "save_all_models": self.save_all_models
        }
        
        # Create the jobs directory if it doesn't exist
        os.makedirs("alphafold_jobs", exist_ok=True)
        
        # Save to file
        job_file = os.path.join("alphafold_jobs", f"job_{self.job_id}.json")
        with open(job_file, 'w') as f:
            json.dump(job_info, f, indent=2)
    
    def _load_job_info(self):
        """Load job information from a file"""
        # Check if we have a jobs directory
        if not os.path.exists("alphafold_jobs"):
            return
        
        # Look for the most recent job file
        job_files = list(Path("alphafold_jobs").glob("job_*.json"))
        if not job_files:
            return
        
        # Sort by modification time (most recent first)
        job_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Load the most recent job
        with open(job_files[0], 'r') as f:
            job_info = json.load(f)
        
        # Populate the attributes
        self.job_id = job_info.get("job_id")
        self.job_name = job_info.get("job_name")
        self.email = job_info.get("email")
        self.results_url = job_info.get("results_url")
        self.job_status = job_info.get("status")
        self.dna_sequence = job_info.get("dna_sequence")
        self.protein_sequence = job_info.get("protein_sequence")
        self.use_multimer = job_info.get("use_multimer", False)
        self.save_all_models = job_info.get("save_all_models", False)