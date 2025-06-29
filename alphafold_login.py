"""
AlphaFold login module using undetected-chromedriver
This module handles authentication to AlphaFold server with improved Chrome handling
"""
import os
import time
import pickle
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import undetected-chromedriver for avoiding detection
import undetected_chromedriver as uc

class AlphaFoldLogin:
    """Class for handling AlphaFold login"""
    
    def __init__(self):
        """Initialize the AlphaFold login handler"""
        self.driver = None
        self.email = None
        self.password = None
        self.cookies_file = "alphafold_cookies.pkl"
        self.screenshots_dir = "login_screenshots"
        
        # Create screenshots directory
        os.makedirs(self.screenshots_dir, exist_ok=True)
    
    def setup(self, email, password):
        """Set up the login handler with credentials
        
        Args:
            email (str): Gmail email address
            password (str): Gmail password
        """
        self.email = email
        self.password = password
    
    def take_screenshot(self, name):
        """Take a screenshot for debugging
        
        Args:
            name (str): Name for the screenshot
        """
        if self.driver:
            try:
                self.driver.save_screenshot(f"{self.screenshots_dir}/{name}.png")
                print(f"Screenshot saved: {name}.png")
            except Exception as e:
                print(f"Failed to save screenshot {name}: {e}")
    
    def init_browser(self, use_profile=True):
        """Initialize a browser that avoids detection with better Chrome handling
        
        Args:
            use_profile (bool): Whether to use a Chrome profile with cookies
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print("Initializing undetected Chrome browser...")
            
            # Create options specifically for undetected-chromedriver
            options = uc.ChromeOptions()
            
            # Set basic options
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            
            # Add user agent
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
            
            # Use a Chrome profile to maintain login state
            if use_profile:
                user_data_dir = os.path.join(os.path.expanduser("~"), "alphafold_chrome_profile")
                os.makedirs(user_data_dir, exist_ok=True)
                options.add_argument(f"--user-data-dir={user_data_dir}")
                print(f"Using Chrome profile at: {user_data_dir}")
            
            # Try different approaches to initialize Chrome
            driver_attempts = [
                # Attempt 1: Use specific version matching
                lambda: uc.Chrome(
                    options=options,
                    version_main=137,  # Match your Chrome version
                    headless=False
                ),
                # Attempt 2: Auto-detect version
                lambda: uc.Chrome(
                    options=options,
                    version_main=None,
                    headless=False
                ),
                # Attempt 3: Use patcher auto
                lambda: uc.Chrome(
                    options=options,
                    use_subprocess=False,
                    headless=False
                ),
            ]
            
            for i, attempt in enumerate(driver_attempts, 1):
                try:
                    print(f"Attempting browser initialization method {i}...")
                    self.driver = attempt()
                    break
                except Exception as e:
                    print(f"Method {i} failed: {e}")
                    if i == len(driver_attempts):
                        raise e
                    continue
            
            if not self.driver:
                raise Exception("All browser initialization methods failed")
            
            # Additional protection via JavaScript execution
            try:
                self.driver.execute_script("""
                    // Overwrite the navigator.webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Remove webdriver from navigator
                    delete navigator.__proto__.webdriver;
                """)
            except Exception as e:
                print(f"Warning: Could not execute anti-detection script: {e}")
            
            print("Undetected Chrome initialized successfully")
            return True
            
        except Exception as e:
            print(f"Error initializing undetected Chrome: {e}")
            return False
    
    def manual_login(self):
        """Login to AlphaFold 3 manually and save cookies
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.driver:
            if not self.init_browser(use_profile=True):
                print("Failed to initialize browser")
                return False
        
        try:
            # Navigate to AlphaFold
            print("Navigating to AlphaFold server...")
            self.driver.get("https://alphafoldserver.com/")
            print("Navigated to AlphaFold homepage")
            self.take_screenshot("1_homepage")
            
            # Wait for page to load
            time.sleep(3)
            
            # Prompt for manual login
            print("\n" + "="*60)
            print("*** MANUAL LOGIN REQUIRED ***")
            print("="*60)
            print("1. Look for 'Continue with Google' or 'Sign in' button")
            print("2. Complete the Google sign-in process in the browser window")
            print("3. Accept all terms of service if prompted")
            print("4. Navigate all the way to the AlphaFold dashboard/submit page")
            print("5. Make sure you can see job submission options")
            print("="*60)
            
            # Keep the browser open for manual interaction
            input("Press Enter once you've successfully logged in and can see the job submission interface...")
            
            # Check if login was successful by looking for expected elements
            self.take_screenshot("2_after_login")
            
            # Save cookies
            cookies = self.driver.get_cookies()
            if cookies:
                with open(self.cookies_file, "wb") as f:
                    pickle.dump(cookies, f)
                print(f"Saved {len(cookies)} cookies to {self.cookies_file}")
                
                # Also save current URL for reference
                current_url = self.driver.current_url
                print(f"Current URL: {current_url}")
                
                return True
            else:
                print("No cookies found - login may not have been successful")
                return False
            
        except Exception as e:
            print(f"Error during manual login: {e}")
            self.take_screenshot("error_manual_login")
            return False
    
    def login_with_cookies(self):
        """Login using saved cookies
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(self.cookies_file):
            print(f"Cookie file not found: {self.cookies_file}")
            print("Please run manual_login() first")
            return False
        
        if not self.driver:
            if not self.init_browser(use_profile=True):
                print("Failed to initialize browser")
                return False
        
        try:
            print("Attempting login with saved cookies...")
            
            # First visit the domain
            self.driver.get("https://alphafoldserver.com")
            time.sleep(2)
            
            # Add cookies to browser
            with open(self.cookies_file, "rb") as f:
                cookies = pickle.load(f)
            
            print(f"Loading {len(cookies)} saved cookies...")
            
            cookies_added = 0
            for cookie in cookies:
                try:
                    # Handle expiry and other problematic attributes
                    cookie_copy = cookie.copy()
                    if 'expiry' in cookie_copy:
                        del cookie_copy['expiry']
                    if 'sameSite' in cookie_copy and cookie_copy['sameSite'] not in ['Strict', 'Lax', 'None']:
                        del cookie_copy['sameSite']
                    
                    self.driver.add_cookie(cookie_copy)
                    cookies_added += 1
                except Exception as e:
                    print(f"Warning: Could not add cookie {cookie.get('name')}: {e}")
            
            print(f"Successfully added {cookies_added} cookies")
            
            # Navigate to main page
            self.driver.get("https://alphafoldserver.com/")
            time.sleep(3)
            self.take_screenshot("3_after_cookie_login")
            
            # Check if login was successful
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()
            
            # Look for signs of successful login
            success_indicators = [
                "submit" in page_source,
                "dashboard" in page_source,
                "logout" in page_source,
                "profile" in page_source,
                "job" in page_source
            ]
            
            if any(success_indicators):
                print("Login successful using cookies!")
                print(f"Current URL: {current_url}")
                return True
            else:
                print("Cookie login failed. Cookies may have expired.")
                print(f"Current URL: {current_url}")
                return False
                
        except Exception as e:
            print(f"Error during cookie login: {e}")
            self.take_screenshot("error_cookie_login")
            return False
    
    def login(self):
        """Login to AlphaFold trying cookies first, then manual login
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Try to login with cookies first
        if os.path.exists(self.cookies_file):
            print("Attempting to login with saved cookies...")
            if self.login_with_cookies():
                return True
            print("Cookie login failed, falling back to manual login...")
        
        # Fall back to manual login
        return self.manual_login()
    
    def get_driver(self):
        """Get the browser driver
        
        Returns:
            WebDriver: The browser driver
        """
        return self.driver
    
    def cleanup(self):
        """Close the browser when done"""
        if self.driver:
            try:
                self.driver.quit()
                print("Browser closed")
            except Exception as e:
                print(f"Error closing browser: {e}")
            finally:
                self.driver = None

if __name__ == "__main__":
    # Example usage
    login_handler = AlphaFoldLogin()
    success = login_handler.login()
    
    if success:
        print("Successfully logged in to AlphaFold!")
        input("Press Enter to close the browser...")
    else:
        print("Failed to login to AlphaFold")
    
    login_handler.cleanup()