"""
AlphaFold Job Submitter - FIXED VERSION
Handles the submission of protein-DNA jobs to AlphaFold 3
"""
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class AlphaFoldJobSubmitter:
    """Handles job submission to AlphaFold 3"""
    
    def __init__(self, driver):
        """Initialize job submitter
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.wait = WebDriverWait(driver, 20)
        self.short_wait = WebDriverWait(driver, 5)
    
    def submit_job(self, protein_sequence, dna_sequence, job_name):
        """Submit a protein-DNA job to AlphaFold
        
        Args:
            protein_sequence (str): Protein sequence
            dna_sequence (str): DNA sequence
            job_name (str): Name for the job
            
        Returns:
            str: Job ID if successful, None if failed
        """
        try:
            print(f"Starting job submission: {job_name}")
            
            # Step 1: Clear existing entities
            if not self._clear_existing_entities():
                print("Warning: Could not clear existing entities")
            
            # Step 2: Add protein entity
            if not self._add_protein_entity(protein_sequence):
                print("Failed to add protein entity")
                return None
            
            # Step 3: Add DNA entity
            if not self._add_dna_entity(dna_sequence):
                print("Failed to add DNA entity")
                return None
            
            # Step 4: Continue to job preview
            if not self._continue_to_preview():
                print("Failed to continue to preview")
                return None
            
            # Step 5: Enter job name and submit
            job_id = self._submit_job_with_name(job_name)
            if job_id:
                print(f"Job submitted successfully with ID: {job_id}")
                return job_id
            else:
                print("Failed to submit job")
                return None
                
        except Exception as e:
            print(f"Error during job submission: {e}")
            return None
    
    def _clear_existing_entities(self):
        """Clear any existing entities from the submission form
        
        Returns:
            bool: True if successful or no entities to clear
        """
        try:
            print("Checking for existing entities to clear...")
            
            # Look for entity options buttons (more_vert icons)
            entity_option_buttons = self.driver.find_elements(
                By.XPATH, 
                "//button[contains(@class, 'mat-mdc-menu-trigger') and contains(@class, 'actions')]"
            )
            
            entities_cleared = 0
            for button in entity_option_buttons:
                try:
                    # Scroll to the button first
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                    time.sleep(0.5)
                    
                    # Click the options button to open menu
                    self.driver.execute_script("arguments[0].click();", button)
                    time.sleep(1)
                    
                    # Look for delete button in the dropdown menu
                    delete_button = self.short_wait.until(
                        EC.element_to_be_clickable((
                            By.XPATH, 
                            "//button[contains(@class, 'mat-mdc-menu-item')]//span[text()='Delete']/.."
                        ))
                    )
                    
                    # Click delete
                    self.driver.execute_script("arguments[0].click();", delete_button)
                    time.sleep(1)
                    entities_cleared += 1
                    
                except Exception as e:
                    print(f"Could not delete entity: {e}")
                    # Try to close any open menus by pressing ESC
                    try:
                        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        time.sleep(0.5)
                    except:
                        pass
                    continue
            
            if entities_cleared > 0:
                print(f"Cleared {entities_cleared} existing entities")
                # Wait a moment for the page to update after clearing entities
                time.sleep(2)
            else:
                print("No existing entities found")
            
            return True
            
        except Exception as e:
            print(f"Error clearing existing entities: {e}")
            return True  # Continue even if clearing fails
    
    def _find_add_entity_button(self):
        """Find the Add entity button using multiple strategies
        
        Returns:
            WebElement: Add entity button if found, None otherwise
        """
        try:
            # Strategy 1: Use the exact XPath you provided
            try:
                button = self.driver.find_element(
                    By.XPATH, 
                    "/html/body/gdm-af-app/gdm-af-side-nav/mat-sidenav-container/mat-sidenav-content/main/gdm-af-server/main/gdm-af-request/main/div[3]/button[1]"
                )
                if button and button.is_displayed() and button.is_enabled():
                    print("Found Add entity button using exact XPath")
                    return button
            except:
                pass
            
            # Strategy 2: Look for button by text content
            button_selectors = [
                "//button[contains(text(), 'Add entity')]",
                "//button[normalize-space(text())='Add entity']",
                "//button[@aria-label='Add entity']",
                "//button[.//span[contains(text(), 'Add entity')]]"
            ]
            
            for selector in button_selectors:
                try:
                    button = self.driver.find_element(By.XPATH, selector)
                    if button and button.is_displayed() and button.is_enabled():
                        print(f"Found Add entity button using selector: {selector}")
                        return button
                except:
                    continue
            
            # Strategy 3: Look for button in the main content area
            try:
                button = self.driver.find_element(
                    By.XPATH, 
                    "//main//div[3]//button[1][contains(text(), 'Add entity')]"
                )
                if button and button.is_displayed() and button.is_enabled():
                    print("Found Add entity button in main content area")
                    return button
            except:
                pass
            
            # Strategy 4: Look for button with class patterns
            class_selectors = [
                "//button[contains(@class, 'mat-mdc-button') and contains(text(), 'Add entity')]",
                "//button[contains(@class, 'mat-button') and contains(text(), 'Add entity')]"
            ]
            
            for selector in class_selectors:
                try:
                    button = self.driver.find_element(By.XPATH, selector)
                    if button and button.is_displayed() and button.is_enabled():
                        print(f"Found Add entity button using class selector: {selector}")
                        return button
                except:
                    continue
            
            print("Could not find Add entity button with any strategy")
            return None
            
        except Exception as e:
            print(f"Error finding Add entity button: {e}")
            return None
    
    def _add_protein_entity(self, protein_sequence):
        """Add protein entity to the submission form
        
        Args:
            protein_sequence (str): Protein amino acid sequence
            
        Returns:
            bool: True if successful
        """
        try:
            print("Adding protein entity...")
            
            # Find and click "Add entity" button
            add_entity_button = self._find_add_entity_button()
            if not add_entity_button:
                print("Could not find Add entity button")
                return False
            
            # Scroll to button to ensure it's visible
            self.driver.execute_script("arguments[0].scrollIntoView(true);", add_entity_button)
            time.sleep(1)
            
            # Click the button
            try:
                add_entity_button.click()
            except Exception:
                # Try JavaScript click if regular click fails
                self.driver.execute_script("arguments[0].click();", add_entity_button)
            
            print("Clicked Add entity button for protein")
            time.sleep(3)  # Wait for entity to be added
            
            # Wait for entity to be added and find the dropdown
            entity_dropdown = None
            dropdown_selectors = [
                "//mat-select[contains(@class, 'sequence-type')]",
                "//mat-select[@role='combobox']",
                "//gdm-af-sequence-entity[1]//mat-select"
            ]
            
            for selector in dropdown_selectors:
                try:
                    entity_dropdown = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"Found entity dropdown using: {selector}")
                    break
                except:
                    continue
            
            if not entity_dropdown:
                raise Exception("Could not find entity type dropdown")
            
            # Click dropdown to open options
            entity_dropdown.click()
            time.sleep(2)
            
            # Select "Protein" option
            protein_option = self.wait.until(
                EC.element_to_be_clickable((
                    By.XPATH, 
                    "//mat-option//span[contains(text(), 'Protein')]/.."
                ))
            )
            protein_option.click()
            time.sleep(2)
            
            # Find and fill protein sequence textarea
            protein_input = self._find_sequence_input(1)  # First entity
            if not protein_input:
                raise Exception("Could not find protein sequence input field")
            
            # Clear and enter protein sequence
            protein_input.clear()
            protein_input.send_keys(protein_sequence)
            time.sleep(1)
            
            print("Protein entity added successfully")
            return True
            
        except Exception as e:
            print(f"Error adding protein entity: {e}")
            return False
    
    def _add_dna_entity(self, dna_sequence):
        """Add DNA entity to the submission form
        
        Args:
            dna_sequence (str): DNA nucleotide sequence
            
        Returns:
            bool: True if successful
        """
        try:
            print("Adding DNA entity...")
            
            # Find and click "Add entity" button again for second entity
            add_entity_button = self._find_add_entity_button()
            if not add_entity_button:
                print("Could not find Add entity button for DNA")
                return False
            
            # Scroll to button to ensure it's visible
            self.driver.execute_script("arguments[0].scrollIntoView(true);", add_entity_button)
            time.sleep(1)
            
            # Click the button
            try:
                add_entity_button.click()
            except Exception:
                # Try JavaScript click if regular click fails
                self.driver.execute_script("arguments[0].click();", add_entity_button)
            
            print("Clicked Add entity button for DNA")
            time.sleep(3)  # Wait for entity to be added
            
            # Find the second entity dropdown (should be the most recently added)
            entity_dropdowns = self.driver.find_elements(
                By.XPATH, "//mat-select[contains(@class, 'sequence-type')]"
            )
            
            if len(entity_dropdowns) < 2:
                raise Exception("Second entity dropdown not found")
            
            # Click the second dropdown
            second_dropdown = entity_dropdowns[-1]  # Last one should be the newest
            second_dropdown.click()
            time.sleep(1)
            
            # Select "DNA" option
            dna_option = self.wait.until(
                EC.element_to_be_clickable((
                    By.XPATH, 
                    "//mat-option//span[contains(text(), 'DNA')]/.."
                ))
            )
            dna_option.click()
            time.sleep(2)
            
            # Find DNA sequence textarea (should be the second one)
            dna_input = self._find_sequence_input(2)  # Second entity
            if not dna_input:
                raise Exception("Could not find DNA sequence input field")
            
            # Clear and enter DNA sequence
            dna_input.clear()
            dna_input.send_keys(dna_sequence)
            time.sleep(1)
            
            print("DNA entity added successfully")
            return True
            
        except Exception as e:
            print(f"Error adding DNA entity: {e}")
            return False
    
    def _find_sequence_input(self, entity_number):
        """Find sequence input field for a specific entity
        
        Args:
            entity_number (int): 1 for first entity, 2 for second entity
            
        Returns:
            WebElement: Sequence input field if found, None otherwise
        """
        try:
            input_selectors = [
                f"//gdm-af-sequence-entity[{entity_number}]//textarea",
                f"(//textarea[contains(@class, 'sequence-input')])[{entity_number}]",
                f"(//textarea[@placeholder='Input'])[{entity_number}]",
                f"#mat-input-{5 + entity_number}",  # Common pattern for mat-input IDs
                f"#mat-input-{3 + entity_number * 2}"  # Alternative pattern
            ]
            
            for selector in input_selectors:
                try:
                    if selector.startswith("#"):
                        element = self.driver.find_element(By.ID, selector.replace("#", ""))
                    else:
                        element = self.driver.find_element(By.XPATH, selector)
                    
                    if element and element.is_displayed() and element.is_enabled():
                        print(f"Found sequence input {entity_number} using selector: {selector}")
                        return element
                except:
                    continue
            
            # Fallback: find all sequence inputs and use the nth one
            all_inputs = self.driver.find_elements(By.XPATH, "//textarea[contains(@class, 'sequence-input')]")
            if len(all_inputs) >= entity_number:
                print(f"Found sequence input {entity_number} using fallback method")
                return all_inputs[entity_number - 1]
            
            print(f"Could not find sequence input field for entity {entity_number}")
            return None
            
        except Exception as e:
            print(f"Error finding sequence input {entity_number}: {e}")
            return None
    
    def _continue_to_preview(self):
        """Click continue to job preview
        
        Returns:
            bool: True if successful
        """
        try:
            print("Continuing to job preview...")
            
            # Find continue button using multiple selectors
            continue_selectors = [
                "//button[contains(text(), 'Continue and preview job')]",
                "//button[normalize-space(text())='Continue and preview job']",
                "//button[.//span[contains(text(), 'Continue and preview job')]]",
                "//button[@aria-label='Continue and preview job']"
            ]
            
            continue_button = None
            for selector in continue_selectors:
                try:
                    continue_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except:
                    continue
            
            if not continue_button:
                raise Exception("Could not find Continue button")
            
            # Scroll to button and click
            self.driver.execute_script("arguments[0].scrollIntoView(true);", continue_button)
            time.sleep(1)
            
            try:
                continue_button.click()
            except Exception:
                # Try JavaScript click if regular click fails
                self.driver.execute_script("arguments[0].click();", continue_button)
            
            print("Clicked Continue and preview job button")
            
            # Wait for preview page to load
            time.sleep(5)
            
            # Check if we're on the preview page by looking for job name input
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "//input[@matinput]"))
                )
                print("Successfully reached job preview page")
                return True
            except TimeoutException:
                print("Could not reach job preview page")
                return False
                
        except Exception as e:
            print(f"Error continuing to preview: {e}")
            return False
    
    def _dismiss_overlays(self):
        """DISABLED: Do not dismiss any overlays to avoid interfering with dialogs"""
        # This method is now disabled to prevent interference with job submission dialogs
        print("Overlay dismissal disabled to preserve dialogs")
        pass

    def _submit_job_with_name(self, job_name):
        """FIXED: Enter job name and submit the job without any overlay dismissal
        
        Args:
            job_name (str): Name for the job
            
        Returns:
            str: Job ID if successful, None if failed
        """
        try:
            print(f"Submitting job with name: {job_name}")
            
            # Wait for the job name dialog to appear
            print("Waiting for job name dialog to appear...")
            time.sleep(5)
            
            # DO NOT DISMISS ANY OVERLAYS - they might be the dialog we need!
            
            # Find job name input with increased timeout
            job_name_input = None
            input_selectors = [
                "/html/body/div[3]/div[2]/div/mat-dialog-container/div/div/gdm-af-preview-dialog/main/form/mat-form-field/div[1]/div/div[2]/input",  # Your exact XPath
                "//mat-dialog-container//input[@matinput]",  # Input in dialog container
                "//gdm-af-preview-dialog//input[@matinput]",  # Input in preview dialog
                "//input[@required and @matinput]",  # Required matinput field
                "//form//input[@matinput]",  # Input in form
                "//mat-form-field//input",  # Input in mat-form-field
                "//div[contains(@class, 'mat-dialog')]//input"  # Any input in dialog
            ]
            
            # Use a longer timeout to allow dialog to fully load
            dialog_wait = WebDriverWait(self.driver, 20)
            
            for selector in input_selectors:
                try:
                    print(f"Trying selector: {selector}")
                    
                    job_name_input = dialog_wait.until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    
                    # Additional check - wait for it to be interactable
                    dialog_wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    
                    if job_name_input.is_displayed() and job_name_input.is_enabled():
                        print(f"Found job name input using: {selector}")
                        break
                    else:
                        print(f"Input found but not interactable with: {selector}")
                        job_name_input = None
                        
                except TimeoutException:
                    print(f"Timeout waiting for input with: {selector}")
                    continue
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue
            
            if not job_name_input:
                # Take a screenshot for debugging
                try:
                    self.driver.save_screenshot("job_name_input_not_found.png")
                    print("Screenshot saved: job_name_input_not_found.png")
                    
                    # Also save page source for debugging
                    with open("page_source_debug.html", "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    print("Page source saved: page_source_debug.html")
                except:
                    pass
                raise Exception("Could not find job name input field")
            
            # Focus on the input field without clicking elsewhere
            print("Focusing on job name input field...")
            self.driver.execute_script("arguments[0].focus();", job_name_input)
            time.sleep(0.5)
            
            # Clear the field using JavaScript to avoid issues
            print("Clearing job name input field...")
            self.driver.execute_script("arguments[0].value = '';", job_name_input)
            time.sleep(0.3)
            
            # Enter the job name using JavaScript to ensure it works
            print(f"Entering job name: '{job_name}'")
            self.driver.execute_script(f"arguments[0].value = '{job_name}';", job_name_input)
            
            # Trigger events to notify the form that the value changed
            self.driver.execute_script("""
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
            """, job_name_input)
            
            time.sleep(0.5)
            
            # Verify the value was entered correctly
            entered_value = job_name_input.get_attribute("value") or ""
            print(f"Value after entering: '{entered_value}'")
            
            # Find submit button
            print("Looking for submit button...")
            submit_selectors = [
                "//button[contains(text(), 'Confirm and submit job')]",
                "//button[normalize-space(text())='Confirm and submit job']",
                "//button[.//span[contains(text(), 'Confirm and submit job')]]",
                "//mat-dialog-container//button[contains(text(), 'Confirm')]",
                "//gdm-af-preview-dialog//button[contains(text(), 'Confirm')]",
                "//button[contains(@class, 'mat-mdc-button') and contains(text(), 'submit')]",
                "//form//button[contains(text(), 'submit')]",
                "//div[contains(@class, 'mat-dialog')]//button[contains(text(), 'Confirm')]"
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    print(f"Trying submit button selector: {selector}")
                    submit_button = dialog_wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"Found submit button using: {selector}")
                    break
                except TimeoutException:
                    print(f"Timeout waiting for submit button with: {selector}")
                    continue
                except Exception as e:
                    print(f"Error with submit selector {selector}: {e}")
                    continue
            
            if not submit_button:
                # Take a screenshot for debugging
                try:
                    self.driver.save_screenshot("submit_button_not_found.png")
                    print("Screenshot saved: submit_button_not_found.png")
                except:
                    pass
                raise Exception("Could not find Submit button")
            
            # Click submit button
            print("Clicking submit button...")
            try:
                self.driver.execute_script("arguments[0].click();", submit_button)
            except Exception as click_error:
                print(f"JavaScript click failed: {click_error}")
                # Try regular click as backup
                submit_button.click()
            
            print("Clicked Confirm and submit job button")
            
            # Wait for submission to complete and try to extract job ID
            time.sleep(5)
            
            # Try to extract job ID from URL or page content
            job_id = self._extract_job_id(job_name)
            
            if job_id:
                print(f"Job submitted with ID: {job_id}")
                return job_id
            else:
                print("Job submitted but could not extract ID")
                return job_name  # Fallback to job name
                
        except Exception as e:
            print(f"Error submitting job: {e}")
            import traceback
            traceback.print_exc()
            return None

    
    def _extract_job_id(self, job_name):
        """Try to extract job ID from page or URL
        
        Args:
            job_name (str): The job name for fallback
            
        Returns:
            str: Job ID if found, otherwise job_name
        """
        try:
            # Method 1: Check URL for job ID
            current_url = self.driver.current_url
            url_match = re.search(r'/job/([a-zA-Z0-9\-_]+)', current_url)
            if url_match:
                job_id = url_match.group(1)
                print(f"Extracted job ID from URL: {job_id}")
                return job_id
            
            # Method 2: Look for job ID in page content
            page_source = self.driver.page_source
            id_patterns = [
                r'job[_\-\s]?id[:\s]+([a-zA-Z0-9\-_]+)',
                r'submission[_\-\s]?id[:\s]+([a-zA-Z0-9\-_]+)',
                r'fold[_\-\s]?id[:\s]+([a-zA-Z0-9\-_]+)'
            ]
            
            for pattern in id_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    job_id = match.group(1)
                    print(f"Extracted job ID from page content: {job_id}")
                    return job_id
            
            # Method 3: Use job name as fallback
            print("Could not extract job ID, using job name as identifier")
            return job_name
            
        except Exception as e:
            print(f"Error extracting job ID: {e}")
            return job_name