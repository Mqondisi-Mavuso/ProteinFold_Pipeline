"""
Fixed AlphaFold login using undetected-chromedriver
This approach is more effective at avoiding Google's automation detection
"""

import os
import time
import pickle
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Need to install: pip install undetected-chromedriver
import undetected_chromedriver as uc

class StealthBrowser:
    """Class for browser automation that avoids detection"""
    
    def __init__(self):
        self.driver = None
        self.cookies_file = "alphafold_cookies.pkl"
        self.screenshots_dir = "browser_screenshots"
    
    def take_screenshot(self, name):
        """Take a screenshot for debugging"""
        os.makedirs(self.screenshots_dir, exist_ok=True)
        if self.driver:
            self.driver.save_screenshot(f"{self.screenshots_dir}/{name}.png")
            print(f"Screenshot saved: {name}.png")
    
    def init_stealth_browser(self, use_profile=False):
        """Initialize a browser that avoids detection"""
        try:
            # Create options specifically for undetected-chromedriver
            options = uc.ChromeOptions()
            
            # Set basic options
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            
            # Add user agent
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
            
            # Use a Chrome profile if requested
            if use_profile:
                # Modify this path for your system
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
    
    def manual_login_and_save_cookies(self):
        """Open browser for manual login and save cookies"""
        if not self.driver:
            if not self.init_stealth_browser(use_profile=True):
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
            
            # Save page source for analysis
            with open("alphafold_page.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            print("Saved page source to alphafold_page.html")
            
            return True
        except Exception as e:
            print(f"Error during manual login: {e}")
            return False
    
    def login_with_cookies(self):
        """Login using saved cookies"""
        if not os.path.exists(self.cookies_file):
            print(f"Cookie file not found: {self.cookies_file}")
            return False
        
        if not self.driver:
            if not self.init_stealth_browser(use_profile=True):
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
    
    def cleanup(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            print("Browser closed")

def main():
    browser = StealthBrowser()
    
    # First run: Manual login and save cookies
    # Uncomment this line for first run, then comment it out
    #browser.manual_login_and_save_cookies()
    
    # Subsequent runs: Use cookies for login
    success = browser.login_with_cookies()
    
    # if success:
    #     print("Successfully logged in to AlphaFold!")
    #     # Now you can continue with your automation tasks
    # else:
    #     print("Login failed!")
    
    # Don't close the browser automatically - let user see the result
    input("Press Enter to close the browser...")
    browser.cleanup()

if __name__ == "__main__":
    main()