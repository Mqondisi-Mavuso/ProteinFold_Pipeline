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
                    # Click the options button to open menu
                    self.driver.execute_script("arguments[0].click();", button)
                    time.sleep(1)
                    
                    # Look for delete button in the dropdown menu
                    delete_button = self.wait.until(
                        EC.element_to_be_clickable((
                            By.XPATH, 
                            "//button[contains(@class, 'mat-mdc-menu-item')]//span[text()='Delete']/.."
                        ))
                    )
                    
                    # Click delete
                    delete_button.click()
                    time.sleep(1)
                    entities_cleared += 1
                    
                except Exception as e:
                    print(f"Could not delete entity: {e}")
                    # Click outside to close any open menus
                    self.driver.find_element(By.TAG_NAME, "body").click()
                    continue
            
            if entities_cleared > 0:
                print(f"Cleared {entities_cleared} existing entities")
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
            
            # Dismiss any overlays first
            self._dismiss_overlays()
            
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
            
            # Dismiss any overlays that might appear after clicking
            self._dismiss_overlays()
            
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
            try:
                entity_dropdown.click()
            except Exception:
                # If click is intercepted, dismiss overlays and try again
                self._dismiss_overlays()
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", entity_dropdown)
            
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
        """Dismiss any overlays that might be blocking interactions"""
        try:
            # Look for overlay backdrops and dismiss them
            overlay_selectors = [
                "//div[contains(@class, 'cdk-overlay-backdrop')]",
                "//div[contains(@class, 'mat-dialog-backdrop')]",
                "//div[contains(@class, 'overlay-backdrop')]"
            ]
            
            for selector in overlay_selectors:
                overlays = self.driver.find_elements(By.XPATH, selector)
                for overlay in overlays:
                    try:
                        if overlay.is_displayed():
                            print("Found overlay backdrop, clicking to dismiss...")
                            self.driver.execute_script("arguments[0].click();", overlay)
                            time.sleep(1)
                    except:
                        pass
                        
            # Press ESC key to close any open dropdowns/dialogs
            try:
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(1)
            except:
                pass
                
        except Exception as e:
            print(f"Error dismissing overlays: {e}")

    def _submit_job_with_name(self, job_name):
        """Enter job name and submit the job
        
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
            
            # Dismiss any overlays that might be blocking interaction
            self._dismiss_overlays()
            
            # Find job name input using the EXACT XPath you provided
            job_name_input = None
            input_selectors = [
                "/html/body/div[3]/div[2]/div/mat-dialog-container/div/div/gdm-af-preview-dialog/main/form/mat-form-field/div[1]/div/div[2]/input",  # Your exact XPath
                "//mat-dialog-container//input[@matinput]",  # Input in dialog container
                "//gdm-af-preview-dialog//input[@matinput]",  # Input in preview dialog
                "//input[@required and @matinput]",  # Required matinput field
                "//form//input[@matinput]",  # Input in form
                "//mat-form-field//input"  # Input in mat-form-field
            ]
            
            for selector in input_selectors:
                try:
                    print(f"Trying selector: {selector}")
                    job_name_input = self.wait.until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    
                    # Check if element is actually visible and interactable
                    if job_name_input.is_displayed() and job_name_input.is_enabled():
                        print(f"Found job name input using: {selector}")
                        break
                    else:
                        print(f"Input found but not interactable with: {selector}")
                        job_name_input = None
                        
                except TimeoutException:
                    print(f"Could not find input with: {selector}")
                    continue
                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue
            
            if not job_name_input:
                # Take a screenshot for debugging
                try:
                    self.driver.save_screenshot("job_name_input_not_found.png")
                    print("Screenshot saved: job_name_input_not_found.png")
                except:
                    pass
                raise Exception("Could not find job name input field")
            
            # Ensure the input field is visible and focused
            print("Scrolling to job name input...")
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", job_name_input)
            time.sleep(2)
            
            # Click to focus on the input field
            print("Clicking on job name input field...")
            try:
                job_name_input.click()
            except Exception as click_error:
                print(f"Regular click failed: {click_error}, trying JavaScript click...")
                self.driver.execute_script("arguments[0].click();", job_name_input)
            
            time.sleep(1)
            
            # Clear the field thoroughly using multiple methods
            print("Clearing job name input field...")
            
            # Method 1: Select all and delete
            try:
                job_name_input.send_keys(Keys.CONTROL + "a")
                time.sleep(0.5)
                job_name_input.send_keys(Keys.DELETE)
                time.sleep(0.5)
            except Exception as e:
                print(f"Method 1 clearing failed: {e}")
            
            # Method 2: Check current value and clear with backspace
            try:
                current_value = job_name_input.get_attribute("value") or ""
                if current_value:
                    print(f"Current value before clearing: '{current_value}'")
                    # Use backspace to clear character by character
                    for _ in range(len(current_value)):
                        job_name_input.send_keys(Keys.BACKSPACE)
                        time.sleep(0.1)
            except Exception as e:
                print(f"Method 2 clearing failed: {e}")
            
            # Method 3: JavaScript clear
            try:
                self.driver.execute_script("arguments[0].value = '';", job_name_input)
                time.sleep(0.5)
            except Exception as e:
                print(f"Method 3 clearing failed: {e}")
            
            # Verify field is cleared
            cleared_value = job_name_input.get_attribute("value") or ""
            print(f"Value after clearing: '{cleared_value}'")
            
            # Enter the new job name
            print(f"Entering job name: '{job_name}'")
            try:
                job_name_input.send_keys(job_name)
                time.sleep(1)
            except Exception as e:
                print(f"Failed to type job name: {e}")
                # Try JavaScript method
                self.driver.execute_script(f"arguments[0].value = '{job_name}';", job_name_input)
                # Trigger input events
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", job_name_input)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", job_name_input)
                time.sleep(1)
            
            # Verify the value was entered correctly
            entered_value = job_name_input.get_attribute("value") or ""
            print(f"Value after entering: '{entered_value}'")
            
            if entered_value != job_name:
                print(f"Warning: Entered value '{entered_value}' doesn't match expected '{job_name}'")
                # Try one more time with JavaScript
                self.driver.execute_script(f"arguments[0].value = '{job_name}';", job_name_input)
                # Trigger change events
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", job_name_input)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", job_name_input)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));", job_name_input)
                time.sleep(1)
                
                # Verify again
                final_value = job_name_input.get_attribute("value") or ""
                print(f"Final value after JavaScript: '{final_value}'")
            
            # Find submit button using multiple selectors
            print("Looking for submit button...")
            submit_selectors = [
                "//button[contains(text(), 'Confirm and submit job')]",
                "//button[normalize-space(text())='Confirm and submit job']",
                "//button[.//span[contains(text(), 'Confirm and submit job')]]",
                "//mat-dialog-container//button[contains(text(), 'Confirm')]",
                "//gdm-af-preview-dialog//button[contains(text(), 'Confirm')]",
                "//button[contains(@class, 'mat-mdc-button') and contains(text(), 'submit')]",
                "//form//button[contains(text(), 'submit')]"
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    print(f"Trying submit button selector: {selector}")
                    submit_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    print(f"Found submit button using: {selector}")
                    break
                except TimeoutException:
                    print(f"Could not find submit button with: {selector}")
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
            
            # Scroll to submit button and click
            print("Scrolling to submit button...")
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_button)
            time.sleep(2)
            
            print("Clicking submit button...")
            try:
                submit_button.click()
            except Exception as click_error:
                print(f"Regular click failed: {click_error}")
                # Try JavaScript click if regular click fails
                self.driver.execute_script("arguments[0].click();", submit_button)
            
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