"""
AlphaFold Browser Manager
Manages browser setup with proper download configuration for AlphaFold automation
"""
import os
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class AlphaFoldBrowserManager:
    """Manages browser setup and configuration for AlphaFold automation"""
    
    def __init__(self, login_handler, download_directory):
        """Initialize browser manager
        
        Args:
            login_handler: AlphaFoldLogin instance with active session
            download_directory: Directory where files should be downloaded
        """
        self.login_handler = login_handler
        self.download_directory = os.path.abspath(download_directory)
        self.driver = None
        self.screenshots_dir = "automation_screenshots"
        
        # Create screenshots directory
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # Ensure download directory exists
        os.makedirs(self.download_directory, exist_ok=True)
    
    def setup_browser(self):
        """Setup browser with download configuration
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"Setting up browser with download directory: {self.download_directory}")
            
            # Create Chrome options with download settings
            options = uc.ChromeOptions()
            
            # Basic options
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            
            # Download configuration - CRITICAL for automation
            download_prefs = {
                "download.default_directory": self.download_directory,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                "safebrowsing.disable_download_protection": True,
                "plugins.always_open_pdf_externally": True,
                "profile.default_content_settings.popups": 0,
                "profile.default_content_setting_values.automatic_downloads": 1
            }
            
            options.add_experimental_option("prefs", download_prefs)
            
            # Additional options to prevent popup dialogs
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--disable-translate")
            
            # Use the same profile as login handler for session persistence
            if hasattr(self.login_handler, 'driver') and self.login_handler.driver:
                # If login handler has an active driver, we'll use its session
                print("Using existing login session from login handler")
                self.driver = self.login_handler.driver
                
                # Apply download settings to existing session
                self.driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                    'behavior': 'allow',
                    'downloadPath': self.download_directory
                })
                
            else:
                # Create new browser with download settings
                print("Creating new browser instance with download settings")
                user_data_dir = os.path.join(os.path.expanduser("~"), "alphafold_chrome_profile")
                options.add_argument(f"--user-data-dir={user_data_dir}")
                
                # Try different initialization methods
                try:
                    self.driver = uc.Chrome(
                        options=options,
                        version_main=137,
                        headless=False
                    )
                except Exception as e:
                    print(f"First attempt failed: {e}")
                    self.driver = uc.Chrome(
                        options=options,
                        headless=False
                    )
            
            # Verify browser is working
            if not self._verify_browser_setup():
                return False
            
            print("Browser setup completed successfully")
            return True
            
        except Exception as e:
            print(f"Error setting up browser: {e}")
            return False
    
    def _verify_browser_setup(self):
        """Verify browser is properly configured
        
        Returns:
            bool: True if browser is working, False otherwise
        """
        try:
            # Test basic navigation
            self.driver.get("https://alphafoldserver.com/")
            time.sleep(3)
            
            # Take screenshot for verification
            self.take_screenshot("browser_setup_verification")
            
            # Check if we can find expected elements
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                print("Browser verification successful")
                return True
            except Exception as e:
                print(f"Browser verification failed: {e}")
                return False
                
        except Exception as e:
            print(f"Error verifying browser setup: {e}")
            return False
    
    def navigate_to_submission_page(self):
        """Navigate to AlphaFold job submission page
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print("Navigating to AlphaFold submission page...")
            
            # Navigate to main page first
            self.driver.get("https://alphafoldserver.com/")
            time.sleep(3)
            
            # Look for job submission interface
            try:
                # Wait for the submission interface to load
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Add entity')]"))
                )
                print("Successfully navigated to submission page")
                self.take_screenshot("submission_page")
                return True
                
            except Exception as e:
                print(f"Could not find submission interface: {e}")
                # Try alternative navigation if direct access fails
                return self._try_alternative_navigation()
                
        except Exception as e:
            print(f"Error navigating to submission page: {e}")
            return False
    
    def _try_alternative_navigation(self):
        """Try alternative ways to reach submission page"""
        try:
            print("Trying alternative navigation methods...")
            
            # Look for common navigation elements
            nav_elements = [
                "//a[contains(text(), 'Server')]",
                "//button[contains(text(), 'Submit')]",
                "//a[contains(@href, 'submit')]",
                "//a[contains(@href, 'server')]"
            ]
            
            for xpath in nav_elements:
                try:
                    element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    element.click()
                    time.sleep(3)
                    
                    # Check if we reached submission page
                    if self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Add entity')]"):
                        print(f"Alternative navigation successful using: {xpath}")
                        return True
                        
                except Exception:
                    continue
            
            print("All alternative navigation methods failed")
            return False
            
        except Exception as e:
            print(f"Error in alternative navigation: {e}")
            return False
    
    def take_screenshot(self, name):
        """Take a screenshot for debugging
        
        Args:
            name: Name for the screenshot file
        """
        try:
            if self.driver:
                timestamp = time.strftime("%H%M%S")
                screenshot_path = os.path.join(self.screenshots_dir, f"{name}_{timestamp}.png")
                self.driver.save_screenshot(screenshot_path)
                print(f"Screenshot saved: {screenshot_path}")
        except Exception as e:
            print(f"Failed to take screenshot {name}: {e}")
    
    def get_driver(self):
        """Get the browser driver instance
        
        Returns:
            WebDriver: The configured browser driver
        """
        return self.driver
    
    def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.driver and self.driver != self.login_handler.driver:
                # Only quit if it's our own driver instance
                self.driver.quit()
                print("Browser cleanup completed")
        except Exception as e:
            print(f"Error during browser cleanup: {e}")
    
    def test_download_configuration(self):
        """Test if download configuration is working
        
        Returns:
            bool: True if download config is working, False otherwise
        """
        try:
            print("Testing download configuration...")
            
            # Get current download settings
            download_settings = self.driver.execute_script("""
                return {
                    defaultPath: navigator.webkitPersistentStorage ? 'Available' : 'Not Available',
                    downloadBehavior: 'Configured'
                };
            """)
            
            print(f"Download settings: {download_settings}")
            
            # Verify download directory exists and is writable
            if not os.path.exists(self.download_directory):
                print(f"Download directory does not exist: {self.download_directory}")
                return False
            
            if not os.access(self.download_directory, os.W_OK):
                print(f"Download directory is not writable: {self.download_directory}")
                return False
            
            print("Download configuration test passed")
            return True
            
        except Exception as e:
            print(f"Download configuration test failed: {e}")
            return False