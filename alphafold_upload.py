"""
AlphaFold job submission module
This module handles submitting jobs to AlphaFold server
"""
import os
import time
import json
import datetime
import re
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class AlphaFoldUploader:
    """Class for submitting jobs to AlphaFold"""
    
    def __init__(self, driver=None):
        """Initialize the AlphaFold uploader
        
        Args:
            driver: Selenium WebDriver from login module
        """
        self.driver = driver
        self.job_name = None
        self.dna_sequence = None
        self.protein_sequence = None
        self.use_multimer = False
        self.save_all_models = False
        self.job_id = None
        self.job_status = None
        self.results_url = None
        self.screenshots_dir = "upload_screenshots"
        
        # Create screenshots directory
        os.makedirs(self.screenshots_dir, exist_ok=True)
    
    def setup(self, job_name, protein_sequence, dna_sequence=None, 
              use_multimer=False, save_all_models=False):
        """Set up the job submission parameters
        
        Args:
            job_name (str): Name for the AlphaFold job
            protein_sequence (str): Protein sequence (FASTA format)
            dna_sequence (str, optional): DNA sequence
            use_multimer (bool): Whether to use the multimer model
            save_all_models (bool): Whether to save all 5 models
        """
        self.job_name = job_name
        self.protein_sequence = protein_sequence
        self.dna_sequence = dna_sequence
        self.use_multimer = use_multimer
        self.save_all_models = save_all_models
    
    def set_driver(self, driver):
        """Set the browser driver from login module
        
        Args:
            driver: Selenium WebDriver
        """
        self.driver = driver
    
    def take_screenshot(self, name):
        """Take a screenshot for debugging
        
        Args:
            name (str): Name for the screenshot
        """
        if self.driver:
            self.driver.save_screenshot(f"{self.screenshots_dir}/{name}.png")
            print(f"Screenshot saved: {name}.png")
    
    def submit_job(self):
        """Submit a new job to AlphaFold 3
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.driver:
            print("No browser driver provided. Please set a driver first.")
            return False
            
        try:
            # Navigate to the submission page
            try:
                # Wait for the submit link to be clickable
                WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.LINK_TEXT, "Server"))
                )
                # Click on the Server link to go to the submission page
                server_link = self.driver.find_element(By.LINK_TEXT, "Server")
                server_link.click()
                print("Clicked on Server link to go to submission page")
                self.take_screenshot("1_submission_page")
            except Exception as e:
                print(f"Error navigating to submission page: {e}")
                # Try direct navigation
                self.driver.get("https://alphafoldserver.com/server")
                print("Directly navigated to submission page")
                self.take_screenshot("1_direct_navigation")
            
            time.sleep(2)  # Wait for page to load
            
            # Fill out the form
            try:
                # Enter job name in the input field
                job_name_field = self.driver.find_element(By.XPATH, "//input[contains(@placeholder, 'job name')]")
                job_name_field.clear()
                job_name_field.send_keys(self.job_name)
                print(f"Entered job name: {self.job_name}")
                self.take_screenshot("2_entered_job_name")
                
                # Open the protein-DNA selection dropdown 
                # (The exact selector will depend on the website's structure)
                try:
                    # First try clicking the dropdown to show options
                    dropdown = self.driver.find_element(By.XPATH, "//div[contains(@class, 'mat-select-trigger') or contains(@role, 'combobox')]")
                    dropdown.click()
                    time.sleep(1)
                    
                    # Then select the Protein option
                    protein_option = self.driver.find_element(By.XPATH, "//mat-option//span[contains(text(), 'Protein')]/..")
                    protein_option.click()
                    print("Selected Protein from dropdown")
                    self.take_screenshot("3_selected_protein")
                except Exception as e:
                    print(f"Error selecting protein type: {e}")
                    # Continue anyway as protein might be the default
                
                # Look for sequence input fields
                try:
                    # Find the protein sequence input field
                    protein_input = self.driver.find_element(By.XPATH, "//textarea[contains(@placeholder, 'sequence') or contains(@placeholder, 'fasta')]")
                    protein_input.clear()
                    protein_input.send_keys(self.protein_sequence)
                    print("Entered protein sequence")
                    self.take_screenshot("4_entered_protein_sequence")
                    
                    # If we're submitting a protein-DNA complex, need to click "Add entity" button
                    if self.dna_sequence:
                        try:
                            add_entity_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Add entity')]")
                            add_entity_button.click()
                            print("Clicked 'Add entity' button")
                            time.sleep(1)
                            
                            # Now select DNA from the new dropdown
                            dna_dropdown = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'mat-select-trigger') or contains(@role, 'combobox')]")[1]
                            dna_dropdown.click()
                            time.sleep(1)
                            
                            dna_option = self.driver.find_element(By.XPATH, "//mat-option//span[contains(text(), 'DNA')]/..")
                            dna_option.click()
                            print("Selected DNA for second entity")
                            
                            # Enter DNA sequence
                            dna_input = self.driver.find_elements(By.XPATH, "//textarea[contains(@placeholder, 'sequence') or contains(@placeholder, 'fasta')]")[1]
                            dna_input.clear()
                            dna_input.send_keys(self.dna_sequence)
                            print("Entered DNA sequence")
                            self.take_screenshot("5_entered_dna_sequence")
                        except Exception as e:
                            print(f"Error adding DNA entity: {e}")
                except Exception as e:
                    print(f"Error entering sequences: {e}")
                
                # Submit the job
                try:
                    submit_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Continue and preview job') or contains(text(), 'Submit') or contains(text(), 'Run')]")
                    submit_button.click()
                    print("Clicked submit/continue button")
                    self.take_screenshot("6_clicked_submit")
                    
                    # Wait for confirmation or additional dialogs
                    time.sleep(3)
                    
                    # Check if there's a confirmation dialog to click through
                    try:
                        confirm_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Submit') or contains(text(), 'Confirm') or contains(text(), 'Run job')]")
                        confirm_button.click()
                        print("Clicked final confirmation button")
                        self.take_screenshot("7_final_confirmation")
                    except Exception as e:
                        print(f"No confirmation button found, continuing: {e}")
                except Exception as e:
                    print(f"Error submitting job: {e}")
                    return False
                
                # Wait for job submission to complete
                time.sleep(5)
                self.take_screenshot("8_after_submission")
                
                # Try to extract job ID
                try:
                    # Look for job ID in URL or page content
                    current_url = self.driver.current_url
                    url_match = re.search(r'job/([a-zA-Z0-9\-_]+)', current_url)
                    
                    if url_match:
                        self.job_id = url_match.group(1)
                        print(f"Extracted job ID from URL: {self.job_id}")
                    else:
                        # Try to find job ID in page content
                        page_source = self.driver.page_source
                        id_match = re.search(r'[Jj]ob\s+ID[:\s]+([a-zA-Z0-9\-_]+)', page_source)
                        if id_match:
                            self.job_id = id_match.group(1)
                            print(f"Extracted job ID from page: {self.job_id}")
                        else:
                            # Generate a placeholder ID
                            self.job_id = f"job_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                            print(f"Could not extract job ID, using placeholder: {self.job_id}")
                except Exception as e:
                    print(f"Error extracting job ID: {e}")
                    self.job_id = f"job_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Store the results URL
                self.results_url = f"https://alphafoldserver.com/job/{self.job_id}"
                print(f"Results URL: {self.results_url}")
                
                print(f"Successfully submitted job with ID: {self.job_id}")
                self.job_status = "Submitted"
                
                # Save job info to a file for later reference
                self._save_job_info()
                
                return True
            except Exception as e:
                print(f"Error during form filling: {e}")
                return False
            
        except Exception as e:
            print(f"Error during job submission: {e}")
            return False
    
    def _save_job_info(self):
        """Save job information to a file for later reference"""
        job_info = {
            "job_id": self.job_id,
            "job_name": self.job_name,
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
        try:
            with open(job_file, 'w') as f:
                json.dump(job_info, f, indent=2)
            print(f"Job info saved to {job_file}")
        except Exception as e:
            print(f"Error saving job info: {e}")
    
    def get_job_id(self):
        """Get the job ID
        
        Returns:
            str: Job ID
        """
        return self.job_id
    
    def get_results_url(self):
        """Get the results URL
        
        Returns:
            str: Results URL
        """
        return self.results_url

if __name__ == "__main__":
    # This module should be imported and used with a driver from the login module
    print("This module should be imported and used with a driver from the login module.")
    print("See alphafold_crawler.py for example usage.")
