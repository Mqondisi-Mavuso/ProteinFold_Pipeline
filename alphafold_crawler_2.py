"""
AlphaFold 3 submission and results retrieval module using Selenium and BeautifulSoup
"""
import os
import time
import json
import requests
import datetime
import re
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
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
        """Initialize the browser for Selenium with WebDriver Manager"""
        # Set up Chrome options
        chrome_options = Options()
        # Uncomment for production, comment out for debugging
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Initialize the driver with WebDriver Manager
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            print("Chrome WebDriver initialized successfully")
            return True
        except Exception as e:
            print(f"Error initializing Chrome WebDriver: {e}")
            return False
    
    def login_to_alphafold(self):
        """Login to AlphaFold 3 with Google account"""
        try:
            # Navigate to AlphaFold 3
            self.driver.get("https://alphafoldserver.com/welcome")
            print("Navigated to AlphaFold homepage")
            
            # Create screenshots directory if it doesn't exist
            os.makedirs("screenshots", exist_ok=True)
            
            # Take a screenshot for debugging
            self.driver.save_screenshot("screenshots/alphafold_home.png")
            
            # Try different ways to find the sign-in element
            signin_link = None
            try:
                # Wait for the page to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.LINK_TEXT, "Sign in"))
                )
                signin_link = self.driver.find_element(By.LINK_TEXT, "Sign in")
                print("Found 'Sign in' link by link text")
            except Exception as e1:
                print(f"Could not find 'Sign in' by link text: {e1}")
                try:
                    # Try partial link text
                    signin_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, "Sign")
                    print("Found 'Sign in' link by partial link text")
                except Exception as e2:
                    print(f"Could not find 'Sign in' by partial link text: {e2}")
                    try:
                        # Try by XPath
                        signin_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Sign in')]")
                        print("Found 'Sign in' link by XPath")
                    except Exception as e3:
                        print(f"Could not find 'Sign in' by XPath: {e3}")
                        try:
                            # Try by CSS selector
                            signin_link = self.driver.find_element(By.CSS_SELECTOR, "a.signin, a.login, button.signin, button.login")
                            print("Found 'Sign in' link by CSS selector")
                        except Exception as e4:
                            print(f"Could not find 'Sign in' by CSS selector: {e4}")
                            # Take a screenshot to see what's on the page
                            self.driver.save_screenshot("screenshots/signin_not_found.png")
                            print("Could not find the sign-in link. Check screenshots for details.")
                            
                            # Dump the page source for debugging
                            with open("screenshots/page_source.html", "w", encoding="utf-8") as f:
                                f.write(self.driver.page_source)
                            
                            # Try one more approach - look for all links and buttons
                            print("Listing all links on the page:")
                            links = self.driver.find_elements(By.TAG_NAME, "a")
                            for i, link in enumerate(links):
                                try:
                                    print(f"Link {i}: text='{link.text}', href='{link.get_attribute('href')}'")
                                    if 'sign' in link.text.lower() or 'login' in link.text.lower():
                                        signin_link = link
                                        print(f"Found potential sign-in link: {link.text}")
                                except:
                                    pass
                            
                            if not signin_link:
                                raise Exception("Sign-in link not found")
            
            # Click on sign in
            signin_link.click()
            print("Clicked on sign-in link")
            self.driver.save_screenshot("screenshots/after_signin_click.png")
            
            # Wait for Google sign-in page
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "identifierId"))
                )
                print("Google sign-in page loaded")
                self.driver.save_screenshot("screenshots/google_signin.png")
                
                # Enter email
                email_field = self.driver.find_element(By.ID, "identifierId")
                email_field.send_keys(self.email)
                email_field.send_keys(Keys.RETURN)
                print(f"Entered email: {self.email}")
                
                # Wait for password field
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "password"))
                )
                self.driver.save_screenshot("screenshots/password_page.png")
                
                # Enter password
                password_field = self.driver.find_element(By.NAME, "password")
                password_field.send_keys(self.password)
                password_field.send_keys(Keys.RETURN)
                print("Entered password")
                
                # Wait for successful login
                print("Waiting for successful login...")
                self.driver.save_screenshot("screenshots/after_password.png")
                
                # Try different selectors for the Submit button
                try:
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.LINK_TEXT, "Submit"))
                    )
                    print("Found 'Submit' link by link text")
                except:
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Submit"))
                        )
                        print("Found 'Submit' link by partial link text")
                    except:
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Submit')]"))
                            )
                            print("Found 'Submit' link by XPath")
                        except:
                            # Take a screenshot to see what's on the page after login
                            self.driver.save_screenshot("screenshots/after_login.png")
                            print("Looking for navigation menu or submit button...")
                            
                            # Look for typical elements that would be present after successful login
                            try:
                                # Try to find a navigation menu or dashboard element
                                nav_elements = self.driver.find_elements(By.TAG_NAME, "nav")
                                print(f"Found {len(nav_elements)} navigation elements")
                                
                                # Look for any buttons or links
                                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                                print(f"Found {len(all_links)} links. Link texts:")
                                for link in all_links:
                                    try:
                                        link_text = link.text.strip()
                                        if link_text:
                                            print(f"- '{link_text}'")
                                    except:
                                        pass
                            except:
                                pass
                
                self.driver.save_screenshot("screenshots/dashboard.png")
                print("Successfully logged in to AlphaFold 3")
                return True
            except Exception as e:
                self.driver.save_screenshot("screenshots/login_error.png")
                print(f"Error during login process: {e}")
                return False
                
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
                if not self.init_browser():
                    return False
            
            # Login if not already logged in
            if not self.login_to_alphafold():
                return False
            
            # Try to find the Submit link and click it
            try:
                # First try the link text
                submit_link = self.driver.find_element(By.LINK_TEXT, "Submit")
                submit_link.click()
                print("Clicked on 'Submit' link")
            except:
                try:
                    # Try partial link text
                    submit_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, "Submit")
                    submit_link.click()
                    print("Clicked on 'Submit' link (partial match)")
                except:
                    try:
                        # Try by XPath
                        submit_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Submit')]")
                        submit_link.click()
                        print("Clicked on 'Submit' link (XPath)")
                    except:
                        # Take a screenshot and try to identify important elements
                        self.driver.save_screenshot("screenshots/submit_link_not_found.png")
                        print("Could not find the Submit link. Looking at available links...")
                        
                        # List all links on the page
                        links = self.driver.find_elements(By.TAG_NAME, "a")
                        print(f"Found {len(links)} links on the page:")
                        for i, link in enumerate(links):
                            try:
                                href = link.get_attribute("href")
                                text = link.text
                                print(f"Link {i}: text='{text}', href='{href}'")
                                
                                # Try to identify a submission link by URL pattern
                                if href and ("submit" in href.lower() or "job" in href.lower() or "new" in href.lower()):
                                    print(f"Potential submission link found: {href}")
                                    link.click()
                                    print(f"Clicked on potential submission link: {text}")
                                    break
                            except:
                                pass
                        else:
                            raise Exception("Could not find any Submit link or equivalent")
            
            # Wait for submission form and take a screenshot
            self.driver.save_screenshot("screenshots/submission_page.png")
            
            try:
                # Wait for job name field
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "jobName"))
                )
                print("Found job name field")
            except:
                # If we can't find the job name field, look for any input fields
                print("Could not find job name field by ID. Looking for alternatives...")
                input_fields = self.driver.find_elements(By.TAG_NAME, "input")
                
                if input_fields:
                    print(f"Found {len(input_fields)} input fields:")
                    for i, field in enumerate(input_fields):
                        try:
                            field_type = field.get_attribute("type")
                            field_name = field.get_attribute("name")
                            field_id = field.get_attribute("id")
                            field_placeholder = field.get_attribute("placeholder")
                            
                            print(f"Field {i}: type='{field_type}', name='{field_name}', id='{field_id}', placeholder='{field_placeholder}'")
                            
                            # Try to identify the job name field
                            if (field_name and "job" in field_name.lower()) or \
                               (field_id and "job" in field_id.lower()) or \
                               (field_placeholder and "job" in field_placeholder.lower()):
                                print(f"Potential job name field found: {field_id or field_name}")
                                job_name_field = field
                                break
                        except:
                            pass
                    else:
                        raise Exception("Could not identify the job name field")
                else:
                    raise Exception("No input fields found on the submission page")
            
            # Fill out the form
            # Job name
            try:
                job_name_field = self.driver.find_element(By.ID, "jobName")
            except:
                # If we couldn't find it by ID, use the one we identified above
                pass
                
            job_name_field.clear()
            job_name_field.send_keys(self.job_name)
            print(f"Entered job name: {self.job_name}")
            
            # Select protein-DNA complex
            try:
                complex_type = self.driver.find_element(By.ID, "complex-type-dna")
                complex_type.click()
                print("Selected protein-DNA complex type")
            except:
                # If we can't find the complex type by ID, look for radio buttons or dropdowns
                print("Could not find complex type selector by ID. Looking for alternatives...")
                
                # Look for radio buttons
                radio_buttons = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                for radio in radio_buttons:
                    try:
                        radio_id = radio.get_attribute("id")
                        radio_name = radio.get_attribute("name")
                        radio_value = radio.get_attribute("value")
                        radio_label = radio.get_attribute("aria-label") or ""
                        
                        print(f"Radio button: id='{radio_id}', name='{radio_name}', value='{radio_value}', label='{radio_label}'")
                        
                        # Try to identify the DNA complex option
                        if (radio_id and "dna" in radio_id.lower()) or \
                           (radio_name and "complex" in radio_name.lower() and radio_value and "dna" in radio_value.lower()) or \
                           ("dna" in radio_label.lower()):
                            radio.click()
                            print(f"Clicked on potential DNA complex option: {radio_id or radio_name}")
                            break
                    except:
                        pass
            
            # Enter protein sequence
            try:
                protein_field = self.driver.find_element(By.ID, "proteinSequence")
                protein_field.clear()
                protein_field.send_keys(self.protein_sequence)
                print("Entered protein sequence")
            except:
                # If we can't find the protein field by ID, look for textareas
                print("Could not find protein sequence field by ID. Looking for alternatives...")
                textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
                
                if len(textareas) >= 1:
                    # Assume first textarea is for protein if we have multiple
                    protein_field = textareas[0]
                    protein_field.clear()
                    protein_field.send_keys(self.protein_sequence)
                    print("Entered protein sequence into first textarea")
                else:
                    raise Exception("Could not find protein sequence input field")
            
            # Enter DNA sequence
            try:
                dna_field = self.driver.find_element(By.ID, "dnaSequence")
                dna_field.clear()
                dna_field.send_keys(self.dna_sequence)
                print("Entered DNA sequence")
            except:
                # If we can't find the DNA field by ID, look for the second textarea
                print("Could not find DNA sequence field by ID. Looking for alternatives...")
                textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
                
                if len(textareas) >= 2:
                    # Assume second textarea is for DNA
                    dna_field = textareas[1]
                    dna_field.clear()
                    dna_field.send_keys(self.dna_sequence)
                    print("Entered DNA sequence into second textarea")
                else:
                    raise Exception("Could not find DNA sequence input field")
            
            # Take a screenshot of the filled form
            self.driver.save_screenshot("screenshots/filled_form.png")
            
            # Select multimer model if requested
            if self.use_multimer:
                try:
                    multimer_option = self.driver.find_element(By.ID, "multimer-model")
                    multimer_option.click()
                    print("Selected multimer model option")
                except:
                    print("Could not find multimer model option - it might not be available")
            
            # Save all models if requested
            if self.save_all_models:
                try:
                    all_models_option = self.driver.find_element(By.ID, "save-all-models")
                    all_models_option.click()
                    print("Selected save all models option")
                except:
                    print("Could not find save all models option - it might not be available")
            
            # Submit the job
            try:
                submit_button = self.driver.find_element(By.ID, "submit-job")
                submit_button.click()
                print("Clicked submit job button")
            except:
                # If we can't find the submit button by ID, look for alternatives
                print("Could not find submit button by ID. Looking for alternatives...")
                
                # Look for buttons
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                submit_found = False
                
                for button in buttons:
                    try:
                        button_text = button.text.lower()
                        button_type = button.get_attribute("type")
                        button_id = button.get_attribute("id")
                        
                        print(f"Button: text='{button_text}', type='{button_type}', id='{button_id}'")
                        
                        if "submit" in button_text or "run" in button_text or "start" in button_text:
                            button.click()
                            print(f"Clicked on potential submit button: {button_text}")
                            submit_found = True
                            break
                    except:
                        pass
                
                if not submit_found:
                    # Try input type=submit
                    submit_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='submit']")
                    if submit_inputs:
                        submit_inputs[0].click()
                        print("Clicked on input type=submit")
                        submit_found = True
                
                if not submit_found:
                    raise Exception("Could not find submit button")
            
            # Take a screenshot after submission
            self.driver.save_screenshot("screenshots/after_submission.png")
            
            # Wait for confirmation
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "job-submitted"))
                )
                print("Job submission confirmation found")
            except:
                # Look for any indication that the job was submitted
                print("Could not find job submission confirmation. Looking for job info...")
                
                # Take another screenshot
                self.driver.save_screenshot("screenshots/submission_result.png")
                
                # Look for job ID in the page source
                page_source = self.driver.page_source
                
                # Try to extract job ID using common patterns
                job_id_patterns = [
                    r'job[_\-\s]?id[:\s]+([a-zA-Z0-9\-_]+)',
                    r'job[_\-\s]?number[:\s]+([a-zA-Z0-9\-_]+)',
                    r'submission[_\-\s]?id[:\s]+([a-zA-Z0-9\-_]+)'
                ]
                
                for pattern in job_id_patterns:
                    match = re.search(pattern, page_source, re.IGNORECASE)
                    if match:
                        self.job_id = match.group(1)
                        print(f"Extracted job ID from page: {self.job_id}")
                        break
                
                if not self.job_id:
                    # If we still don't have a job ID, check the URL
                    current_url = self.driver.current_url
                    print(f"Current URL: {current_url}")
                    
                    # Try to extract job ID from URL
                    url_match = re.search(r'job/([a-zA-Z0-9\-_]+)', current_url)
                    if url_match:
                        self.job_id = url_match.group(1)
                        print(f"Extracted job ID from URL: {self.job_id}")
                    else:
                        raise Exception("Could not find job submission confirmation or extract job ID")
            
            # Get the job ID from the confirmation page if we haven't already
            if not self.job_id:
                try:
                    job_info = self.driver.find_element(By.CLASS_NAME, "job-info").text
                    job_id_match = re.search(r'Job ID:[\s]*([a-zA-Z0-9\-_]+)', job_info)
                    if job_id_match:
                        self.job_id = job_id_match.group(1)
                        print(f"Extracted job ID: {self.job_id}")
                    else:
                        # Just take the text as is
                        self.job_id = job_info.split("Job ID:")[1].strip().split()[0]
                        print(f"Extracted raw job ID: {self.job_id}")
                except Exception as e:
                    print(f"Error extracting job ID: {e}")
                    self.job_id = f"unknown_job_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Store the results URL
            self.results_url = f"https://alphafold.ebi.ac.uk/job/{self.job_id}"
            print(f"Results URL: {self.results_url}")
            
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
                if not self.init_browser():
                    return "Unknown"
            
            # Login if not already logged in
            if not self.login_to_alphafold():
                return "Unknown"
            
            # Navigate to job results page
            self.driver.get(f"https://alphafold.ebi.ac.uk/job/{self.job_id}")
            print(f"Navigated to job results page: {self.job_id}")
            
            # Take a screenshot of the job status page
            self.driver.save_screenshot("screenshots/job_status.png")
            
            # Wait for status element
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "job-status"))
                )
                
                # Get the status
                status_element = self.driver.find_element(By.CLASS_NAME, "job-status")
                status_text = status_element.text.strip()
                print(f"Found status element: {status_text}")
                
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
            except:
                # If we can't find the job-status class, try alternative approaches
                print("Could not find job status by class. Looking for status indicators...")
                
                # Look for common status words in the page
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
                if not self.init_browser():
                    return False
            
            # Login if not already logged in
            if not self.login_to_alphafold():
                return False
            
            # Navigate to job results page
            self.driver.get(f"https://alphafold.ebi.ac.uk/job/{self.job_id}")
            print(f"Navigated to job results page for download: {self.job_id}")
            
            # Take a screenshot of the results page
            self.driver.save_screenshot("screenshots/results_page.png")
            
            # Try to find the download link
            download_link = None
            try:
                # First try by link text
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.LINK_TEXT, "Download results"))
                )
                download_link = self.driver.find_element(By.LINK_TEXT, "Download results")
                print("Found download link by link text")
            except:
                try:
                    # Try partial link text
                    download_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, "Download")
                    print("Found download link by partial link text")
                except:
                    try:
                        # Try by XPath
                        download_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Download')]")
                        print("Found download link by XPath")
                    except:
                        # Try by href pattern
                        links = self.driver.find_elements(By.TAG_NAME, "a")
                        for link in links:
                            try:
                                href = link.get_attribute("href")
                                if href and ("download" in href.lower() or ".zip" in href.lower()):
                                    download_link = link
                                    print(f"Found download link by href pattern: {href}")
                                    break
                            except:
                                pass
            
            if not download_link:
                print("Could not find the download link")
                self.driver.save_screenshot("screenshots/download_link_not_found.png")
                return False
            
            # Get the download URL
            # Get the download URL
            download_url = download_link.get_attribute("href")
            print(f"Download URL: {download_url}")
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            job_dir = os.path.join(output_dir, self.job_id)
            os.makedirs(job_dir, exist_ok=True)
            
            # Download the result files
            try:
                print(f"Downloading results from {download_url}")
                # Use requests to download the file
                response = requests.get(download_url, stream=True)
                
                if response.status_code == 200:
                    zip_path = os.path.join(job_dir, f"{self.job_id}_results.zip")
                    total_size = int(response.headers.get('content-length', 0))
                    print(f"Total file size: {total_size} bytes")
                    
                    # Write the file with progress tracking
                    with open(zip_path, 'wb') as f:
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                percent = int(100 * downloaded / total_size) if total_size > 0 else 0
                                if downloaded % 1048576 == 0:  # Report every 1MB
                                    print(f"Downloaded: {downloaded} bytes ({percent}%)")
                    
                    print(f"Results downloaded to {zip_path}")
                    
                    # Also save the results page HTML for reference
                    page_html = self.driver.page_source
                    html_path = os.path.join(job_dir, f"{self.job_id}_results.html")
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(page_html)
                    
                    print(f"Results page saved to {html_path}")
                    return True
                else:
                    print(f"Failed to download results: HTTP {response.status_code}")
                    print(f"Response headers: {response.headers}")
                    return False
            except Exception as e:
                print(f"Error downloading results file: {e}")
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
        try:
            with open(job_file, 'w') as f:
                json.dump(job_info, f, indent=2)
            print(f"Job info saved to {job_file}")
        except Exception as e:
            print(f"Error saving job info: {e}")
    
    def _load_job_info(self):
        """Load job information from a file"""
        # Check if we have a jobs directory
        if not os.path.exists("alphafold_jobs"):
            print("No alphafold_jobs directory found")
            return
        
        # Look for the most recent job file
        job_files = list(Path("alphafold_jobs").glob("job_*.json"))
        if not job_files:
            print("No job files found in alphafold_jobs directory")
            return
        
        # Sort by modification time (most recent first)
        job_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        try:
            # Load the most recent job
            most_recent_job = str(job_files[0])
            print(f"Loading most recent job file: {most_recent_job}")
            
            with open(most_recent_job, 'r') as f:
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
            
            print(f"Loaded job info for job ID: {self.job_id}")
        except Exception as e:
            print(f"Error loading job info: {e}")
    