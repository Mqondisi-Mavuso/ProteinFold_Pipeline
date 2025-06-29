"""
Example of cookie-based authentication approach
This avoids Google's login security blocks by using existing cookies from a manual login session
"""

import os
import json
import pickle
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class CookieAuthExample:
    """Example class for cookie-based authentication"""
    
    def __init__(self):
        self.driver = None
        self.cookies_file = "alphafold_cookies.pkl"
        
    def init_browser(self):
        """Initialize browser with standard options"""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            return True
        except Exception as e:
            print(f"Error initializing Chrome WebDriver: {e}")
            return False
    
    def save_cookies(self):
        """Save current browser cookies to file
        
        Run this function once after manually logging in
        """
        if not self.driver:
            self.init_browser()
            
        # Navigate to AlphaFold
        self.driver.get("https://alphafoldserver.com/welcome")
        
        # Prompt for manual login
        print("\n*** MANUAL LOGIN REQUIRED ***")
        print("1. Please complete the Google sign-in process in the browser window")
        print("2. Accept all terms of service if prompted")
        print("3. Navigate all the way to the AlphaFold dashboard/submit page")
        input("Press Enter once you've successfully logged in...")
        
        # Save the cookies
        cookies = self.driver.get_cookies()
        
        # Save cookies to file using pickle (binary format)
        with open(self.cookies_file, "wb") as f:
            pickle.dump(cookies, f)
        
        print(f"Saved {len(cookies)} cookies to {self.cookies_file}")
        
        # Clean up
        self.driver.quit()
        self.driver = None
    
    def login_with_cookies(self):
        """Login using saved cookies"""
        if not os.path.exists(self.cookies_file):
            print(f"Cookie file not found: {self.cookies_file}")
            print("Please run the save_cookies() method first")
            return False
            
        if not self.driver:
            self.init_browser()
        
        # First, visit the domain to enable cookie setting
        self.driver.get("https://alphafoldserver.com")
        
        # Load the cookies
        with open(self.cookies_file, "rb") as f:
            cookies = pickle.load(f)
        
        # Add cookies to browser
        for cookie in cookies:
            # Some cookies may cause issues, so handle exceptions
            try:
                # Remove problematic attributes that might cause errors
                if 'expiry' in cookie:
                    del cookie['expiry']
                
                self.driver.add_cookie(cookie)
            except Exception as e:
                print(f"Warning: Could not add cookie {cookie.get('name')}: {e}")
        
        # Navigate back to the main page
        self.driver.get("https://alphafoldserver.com/welcome")
        
        # Check if login was successful
        time.sleep(2)
        
        # Look for typical elements present after login
        if "submit" in self.driver.page_source.lower() or "dashboard" in self.driver.page_source.lower():
            print("Login successful using cookies!")
            return True
        else:
            print("Cookie login failed. Cookies may have expired.")
            return False

def example_usage():
    """Example of how to use the cookie authentication"""
    cookie_auth = CookieAuthExample()
    
    # First-time setup: Manually log in and save cookies
    # Run this once, then comment it out for future runs
    cookie_auth.save_cookies()
    
    # For subsequent runs, use saved cookies
    #success = cookie_auth.login_with_cookies()
    
    if success:
        print("Successfully logged in using cookies!")
        # Now you can perform actions like submitting jobs
        # ...
    else:
        print("Cookie login failed!")
    
    # Clean up
    if cookie_auth.driver:
        cookie_auth.driver.quit()

if __name__ == "__main__":
    example_usage()
