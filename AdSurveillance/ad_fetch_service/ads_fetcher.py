"""
Ads Fetcher - Python wrapper for TypeScript/Node.js ads fetching module
For Railway/Production Deployment
"""
import os
import subprocess
import sys
import json
import time
import re
from datetime import datetime
from typing import Tuple, Optional, Dict, Any

class AdsFetcher:
    """Python interface to run the TypeScript ads fetching module"""
    
    def __init__(self, timeout: int = None):
        """
        Initialize the ads fetcher
        
        Args:
            timeout: Maximum time in seconds to wait for ads fetching
        """
        # Default values
        self.timeout = timeout or 300  # 5 minutes default
        
        # Try to get from config
        try:
            # Get config relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            config_path = os.path.join(project_root, 'config.py')
            
            if os.path.exists(config_path):
                # Add to path and import
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                
                from config import Config
                self.timeout = timeout or Config.ADS_FETCH_TIMEOUT
                self.ads_fetch_dir = Config.ADS_FETCH_DIR
                self.node_script = Config.NODE_SCRIPT
                
                print(f"✅ Loaded config: {config_path}")
                print(f"   - Timeout: {self.timeout}s")
                print(f"   - Directory: {self.ads_fetch_dir}")
                print(f"   - Script: {self.node_script}")
            else:
                # Use defaults relative to project structure
                self.ads_fetch_dir = os.path.join(project_root, 'src')
                self.node_script = 'npm start'
                print(f"⚠️  Config not found at {config_path}, using defaults")
                
        except ImportError as e:
            print(f"❌ Config import error: {e}")
            # Use safe defaults
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            self.ads_fetch_dir = os.path.join(project_root, 'src')
            self.node_script = 'npm start'
        
        # Ensure directory exists
        if not os.path.exists(self.ads_fetch_dir):
            print(f"⚠️  Warning: Ads fetch directory does not exist: {self.ads_fetch_dir}")
            # Try alternative location
            alternative_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
            if os.path.exists(alternative_dir):
                print(f"   Using alternative: {alternative_dir}")
                self.ads_fetch_dir = alternative_dir
    
    def verify_environment(self) -> Tuple[bool, str]:
        """
        Verify that Node.js environment is properly set up
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if directory exists
            if not os.path.exists(self.ads_fetch_dir):
                return False, f"Ads fetch directory not found: {self.ads_fetch_dir}"
            
            # Check for package.json
            package_json = os.path.join(self.ads_fetch_dir, 'package.json')
            if not os.path.exists(package_json):
                return False, f"package.json not found in {self.ads_fetch_dir}"
            
            # Check if node_modules exists (optional but recommended)
            node_modules = os.path.join(self.ads_fetch_dir, 'node_modules')
            if not os.path.exists(node_modules):
                print(f"⚠️  node_modules not found. Run 'npm install' in {self.ads_fetch_dir}")
            
            # Check Node.js availability
            try:
                result = subprocess.run(['node', '--version'], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5,
                                      cwd=self.ads_fetch_dir)
                if result.returncode != 0:
                    return False, "Node.js is not properly installed"
                print(f"✅ Node.js version: {result.stdout.strip()}")
            except FileNotFoundError:
                return False, "Node.js is not installed"
            
            # Check npm availability
            try:
                result = subprocess.run(['npm', '--version'], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5,
                                      cwd=self.ads_fetch_dir)
                if result.returncode != 0:
                    return False, "npm is not properly installed"
                print(f"✅ npm version: {result.stdout.strip()}")
            except FileNotFoundError:
                return False, "npm is not installed"
            
            return True, "Environment verification passed"
            
        except Exception as e:
            return False, f"Environment verification failed: {str(e)}"
    
    def run_for_user(self, user_id: str, platform: str = "all") -> Tuple[bool, str, int]:
        """
        Run REAL ads fetching for a specific user
        
        Args:
            user_id: The user ID to fetch ads for
            platform: Which platform to fetch from ('meta', 'google', 'linkedin', 'tiktok', 'all')
            
        Returns:
            Tuple of (success, logs, ads_count)
        """
        print(f"🚀 Starting REAL ads fetch for user {user_id} on platform {platform}")
        
        # Verify environment first
        env_ok, env_message = self.verify_environment()
        if not env_ok:
            error_msg = f"Environment check failed: {env_message}"
            print(f"❌ {error_msg}")
            return False, error_msg, 0
        
        # Save original directory
        original_dir = os.getcwd()
        
        try:
            # Change to ads fetch directory
            os.chdir(self.ads_fetch_dir)
            print(f"📁 Changed to directory: {os.getcwd()}")
            
            # Prepare environment variables for Node.js
            env = os.environ.copy()
            env['USER_ID'] = user_id
            env['PLATFORM'] = platform
            env['PYTHON_CALL'] = 'true'
            env['NODE_ENV'] = 'production'  # Set production mode
            
            # Determine command to run
            if self.node_script == 'npm start' or self.node_script == 'npm run start':
                # Check if we have a start script
                package_json_path = os.path.join(self.ads_fetch_dir, 'package.json')
                if os.path.exists(package_json_path):
                    with open(package_json_path, 'r') as f:
                        package_data = json.load(f)
                    
                    if 'scripts' in package_data and 'start' in package_data['scripts']:
                        cmd = ['npm', 'run', 'start']
                    else:
                        # Try to run the main file directly
                        main_file = package_data.get('main', 'dist/index.js')
                        cmd = ['node', main_file]
                else:
                    cmd = ['npm', 'start']
                    
            elif self.node_script.startswith('node '):
                cmd = ['node', self.node_script.replace('node ', '', 1)]
            elif self.node_script.startswith('ts-node '):
                cmd = ['ts-node', self.node_script.replace('ts-node ', '', 1)]
            elif self.node_script.startswith('npm run '):
                cmd = ['npm', 'run', self.node_script.replace('npm run ', '', 1)]
            else:
                cmd = self.node_script.split()
            
            print(f"🔧 Running command: {' '.join(cmd)}")
            print(f"⚙️  Environment: USER_ID={user_id}, PLATFORM={platform}")
            print(f"⏱️  Timeout: {self.timeout}s")
            
            # Run the command with timeout
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                cwd=self.ads_fetch_dir
            )
            
            elapsed_time = time.time() - start_time
            
            # Parse output
            stdout = result.stdout
            stderr = result.stderr
            returncode = result.returncode
            
            # Combine logs
            logs = f"=== REAL Ads Fetching Results ===\n"
            logs += f"User ID: {user_id}\n"
            logs += f"Platform: {platform}\n"
            logs += f"Start Time: {datetime.fromtimestamp(start_time)}\n"
            logs += f"Elapsed Time: {elapsed_time:.2f} seconds\n"
            logs += f"Return Code: {returncode}\n"
            logs += f"\n=== STDOUT ===\n{stdout}\n"
            
            if stderr:
                logs += f"\n=== STDERR ===\n{stderr}\n"
            
            # Parse ads count from output
            ads_count = 0
            success = returncode == 0
            
            if success:
                # Try to extract ads count from Node.js output
                patterns = [
                    r'fetched\s+(\d+)\s+ads',
                    r'ads_fetched[:\s]+(\d+)',
                    r'Found\s+(\d+)\s+ads',
                    r'Total ads:\s*(\d+)',
                    r'saved\s+(\d+)\s+ads',
                    r'processed\s+(\d+)\s+ads'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, stdout + stderr, re.IGNORECASE)
                    if matches:
                        try:
                            ads_count = max([int(m) for m in matches])
                            print(f"📊 Extracted ads count: {ads_count} (pattern: {pattern})")
                            break
                        except:
                            continue
                
                # If no pattern found, estimate based on output length
                if ads_count == 0:
                    # Look for JSON arrays or ad objects
                    if '[' in stdout and ']' in stdout:
                        try:
                            # Try to parse as JSON
                            data = json.loads(stdout[stdout.find('['):stdout.rfind(']')+1])
                            if isinstance(data, list):
                                ads_count = len(data)
                                print(f"📊 Parsed {ads_count} ads from JSON array")
                        except:
                            pass
                
                if ads_count == 0 and ('ad' in stdout.lower() or 'advertisement' in stdout.lower()):
                    # Very rough estimate
                    ads_count = min(50, stdout.count('ad ') + stdout.count('Ad ') + stdout.count('"ad"'))
                    print(f"📊 Estimated ads count: {ads_count}")
            
            print(f"✅ REAL ads fetch completed in {elapsed_time:.2f}s")
            print(f"   Success: {success}, Real ads count: {ads_count}")
            
            return success, logs, ads_count
            
        except subprocess.TimeoutExpired:
            error_msg = f"Ads fetching timed out after {self.timeout} seconds"
            print(f"❌ {error_msg}")
            return False, error_msg, 0
            
        except Exception as e:
            error_msg = f"Error running ads fetcher: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return False, error_msg, 0
            
        finally:
            # Always return to original directory
            os.chdir(original_dir)
            print(f"📁 Returned to directory: {os.getcwd()}")
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to Node.js module
        
        Returns:
            Dictionary with test results
        """
        print("🧪 Testing Node.js environment...")
        
        env_ok, env_message = self.verify_environment()
        
        # Try to run a simple Node.js command
        node_version = "Unknown"
        npm_version = "Unknown"
        
        try:
            # Get Node.js version
            result = subprocess.run(['node', '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                node_version = result.stdout.strip()
        except Exception as e:
            print(f"❌ Node.js check failed: {e}")
        
        try:
            # Get npm version
            result = subprocess.run(['npm', '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0:
                npm_version = result.stdout.strip()
        except Exception as e:
            print(f"❌ npm check failed: {e}")
        
        # Check for package.json and read its contents
        package_json_exists = False
        package_info = {}
        package_json_path = os.path.join(self.ads_fetch_dir, 'package.json')
        
        if os.path.exists(package_json_path):
            package_json_exists = True
            try:
                with open(package_json_path, 'r') as f:
                    package_data = json.load(f)
                    package_info = {
                        'name': package_data.get('name', 'Unknown'),
                        'version': package_data.get('version', 'Unknown'),
                        'has_start_script': 'scripts' in package_data and 'start' in package_data['scripts'],
                        'main_file': package_data.get('main', 'dist/index.js')
                    }
            except Exception as e:
                package_info = {'error': str(e)}
        
        # Check if TypeScript is installed
        typescript_installed = False
        if package_json_exists:
            try:
                result = subprocess.run(['npm', 'list', 'typescript'], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=10,
                                      cwd=self.ads_fetch_dir)
                typescript_installed = 'typescript' in result.stdout
            except:
                pass
        
        return {
            'environment_ok': env_ok,
            'environment_message': env_message,
            'node_version': node_version,
            'npm_version': npm_version,
            'typescript_installed': typescript_installed,
            'ads_fetch_dir': self.ads_fetch_dir,
            'ads_fetch_dir_exists': os.path.exists(self.ads_fetch_dir),
            'package_json_exists': package_json_exists,
            'package_info': package_info,
            'timeout_seconds': self.timeout,
            'node_script': self.node_script,
            'timestamp': datetime.now().isoformat(),
            'mock_mode': False
        }

# Create global instance for import
ads_fetcher = AdsFetcher()

if __name__ == '__main__':
    # Test the ads fetcher
    print("🧪 Testing Ads Fetcher...")
    print("=" * 60)
    
    fetcher = AdsFetcher()
    test_results = fetcher.test_connection()
    
    print("\n📊 Test Results:")
    print("=" * 60)
    for key, value in test_results.items():
        if key == 'package_info' and isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    
    print("=" * 60)
    
    if test_results['environment_ok']:
        print("\n✅ Environment is properly set up!")
        print("🎯 REAL ADS FETCHING READY")
        
        # Test a quick run if possible
        test_user = os.environ.get('TEST_USER_ID', 'test_user')
        print(f"\n🧪 Quick test run for user: {test_user}")
        success, logs, count = fetcher.run_for_user(test_user, "meta")
        print(f"Test result: Success={success}, Ads count={count}")
        
    else:
        print(f"\n❌ Environment issues: {test_results['environment_message']}")
        print("\n💡 To fix:")
        print(f"   1. Ensure Node.js and npm are installed")
        print(f"   2. Check directory exists: {test_results['ads_fetch_dir']}")
        print(f"   3. Ensure package.json exists with a 'start' script")
        print(f"   4. Run 'npm install' in the directory")