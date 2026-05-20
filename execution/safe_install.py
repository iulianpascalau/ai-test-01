#!/usr/bin/env python3
import sys
import subprocess
import urllib.request
import json
import re
import os

def is_stable_version(version_str):
    """
    Checks if a version string implies an unstable release.
    (alpha, beta, rc, dev, post, etc.)
    We want pure semver or simple numbered versions.
    """
    unstable_patterns = [r'a', r'b', r'rc', r'dev', r'pre']
    for pattern in unstable_patterns:
        if re.search(pattern, version_str, re.IGNORECASE):
            return False
    return True

def get_latest_stable_version(package_name):
    """Fetches the latest stable version from PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
            # The 'info' dict has the 'version' which is the latest upload
            latest_version = data['info']['version']
            
            # If the latest is stable, we use it.
            if is_stable_version(latest_version):
                return latest_version
                
            # If latest is unstable, we look through releases for the newest stable one
            releases = data['releases']
            stable_releases = [v for v in releases.keys() if is_stable_version(v)]
            if not stable_releases:
                return None
            
            # Simple fallback to return the last stable we find
            return stable_releases[-1]
            
    except Exception as e:
        print(f"Error fetching data from PyPI for '{package_name}': {e}")
        return None

def update_requirements(package_name, version):
    """Appends the installed package to requirements.txt if not already present."""
    req_files = ["requirements.txt", "backend/requirements.txt"]
    entry = f"{package_name}=={version}"
    
    for req_file in req_files:
        if os.path.exists(req_file):
            with open(req_file, 'r') as f:
                if package_name.lower() in f.read().lower():
                    print(f"{package_name} is already in {req_file}.")
                    continue
                    
            with open(req_file, 'a') as f:
                f.write(f"\n{entry}\n")
            print(f"Added {entry} to {req_file}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python safe_install.py <package_name>")
        sys.exit(1)
        
    package_name = sys.argv[1]
    print(f"Checking PyPI for stable versions of '{package_name}'...")
    
    stable_version = get_latest_stable_version(package_name)
    if not stable_version:
        print(f"Could not find a stable version for '{package_name}' or package does not exist.")
        sys.exit(1)
        
    print(f"Found stable version: {stable_version}. Proceeding with installation...")
    
    # Run pip install using the current python executable's environment
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", f"{package_name}=={stable_version}"])
        print(f"Successfully installed {package_name}=={stable_version}")
        update_requirements(package_name, stable_version)
    except subprocess.CalledProcessError as e:
        print(f"Failed to install {package_name}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
