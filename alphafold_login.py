"""
AlphaFold login module using undetected-chromedriver
This module handles authentication to AlphaFold server
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
            self.driver.save_screenshot(f"{self.screenshots_dir}/{name}.png")
            print(f"Screenshot saved: {name}.png")
    
    def init_browser(self, use_profile=True):
        """Initialize a browser that avoids detection
        
        Args:
            use_profile (bool): Whether to use a Chrome profile with cookies
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create options specifically for undetected-chromedriver
            options = uc.ChromeOptions()
            
            # Set basic options
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            
            # Add user agent
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
            
            # Use a Chrome profile to maintain login state
            if use_profile:
                user_data_dir = os.path.join(os.path.expanduser("~"), "alphafold_chrome_profile")
                os.makedirs(user_data_dir, exist_ok=True)
                options.add_argument(f"--user-data-dir={user_data_dir}")
                print(f"Using Chrome profile at: {user_data_dir}")
            
            # Initialize undetected Chrome
            self.driver = uc.Chrome(
                options=options,
                driver_executable_path=None,  # Auto download
                version_main=None,  # Auto detect
                headless=False  # Must be False for Google login
            )
            
            # Additional protection via JavaScript execution
            self.driver.execute_script("""
                // Overwrite the navigator.webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
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
            self.driver.get("https://alphafoldserver.com/welcome")
            print("Navigated to AlphaFold homepage")
            self.take_screenshot("1_homepage")
            
            # Prompt for manual login
            print("\n*** MANUAL LOGIN REQUIRED ***")
            print("1. Please manually click 'Continue with Google'")
            print("2. Complete the Google sign-in process in the browser window")
            print("3. Accept all terms of service if prompted")
            print("4. Navigate all the way to the AlphaFold dashboard/submit page")
            input("Press Enter once you've successfully logged in...")
            
            # Check if login was successful
            self.take_screenshot("2_after_login")
            
            # Save cookies
            cookies = self.driver.get_cookies()
            with open(self.cookies_file, "wb") as f:
                pickle.dump(cookies, f)
            print(f"Saved {len(cookies)} cookies to {self.cookies_file}")
            
            return True
        except Exception as e:
            print(f"Error during manual login: {e}")
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
            # First visit the domain
            self.driver.get("https://alphafoldserver.com")
            
            # Add cookies to browser
            with open(self.cookies_file, "rb") as f:
                cookies = pickle.load(f)
            
            for cookie in cookies:
                try:
                    # Handle expiry
                    if 'expiry' in cookie:
                        del cookie['expiry']
                    
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"Warning: Could not add cookie {cookie.get('name')}: {e}")
            
            # Navigate to main page
            self.driver.get("https://alphafoldserver.com/welcome")
            self.take_screenshot("3_after_cookie_login")
            
            # Check if login was successful
            time.sleep(2)
            
            if "submit" in self.driver.page_source.lower() or "dashboard" in self.driver.page_source.lower():
                print("Login successful using cookies!")
                return True
            else:
                print("Cookie login failed. Cookies may have expired.")
                return False
        except Exception as e:
            print(f"Error during cookie login: {e}")
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
            self.driver.quit()
            self.driver = None
            print("Browser closed")

if __name__ == "__main__":
    # Example usage
    login_handler = AlphaFoldLogin()
    login_handler.setup("your.email@gmail.com", "your_password")
    success = login_handler.login()
    
    if success:
        print("Successfully logged in to AlphaFold!")
    else:
        print("Failed to login to AlphaFold")
    
    # Keep browser open for inspection
    input("Press Enter to close the browser...")
    login_handler.cleanup()
