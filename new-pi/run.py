#!/usr/bin/env python3
"""
Run script for the waste detection system that handles permissions and dependencies.
"""
import os
import sys
import subprocess
import grp
import pwd

def get_venv_python():
    """Get the path to the virtual environment's Python interpreter."""
    # Check if VIRTUAL_ENV is set
    venv_path = os.getenv('VIRTUAL_ENV')
    if venv_path:
        # Use the current virtual environment
        return os.path.join(venv_path, 'bin', 'python')
    
    # Check for venv directory in current folder
    if os.path.exists('venv'):
        return os.path.abspath(os.path.join('venv', 'bin', 'python'))
    
    # Fallback to system Python
    return sys.executable

def check_and_fix_permissions():
    """Check and fix permissions for hardware access."""
    username = os.getenv('SUDO_USER') or os.getenv('USER')
    if not username:
        print("Error: Could not determine current user")
        return False
        
    # Required groups
    required_groups = ['video', 'gpio', 'dialout', 'tty']  # Added tty group
    
    # Check group membership
    user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
    
    # Add user to required groups
    for group in required_groups:
        if group not in user_groups:
            print(f"Adding user to {group} group...")
            try:
                subprocess.run(['sudo', 'usermod', '-a', '-G', group, username], check=True)
                print(f"Added to {group} group. Please log out and log back in for changes to take effect.")
            except subprocess.CalledProcessError as e:
                print(f"Error adding user to {group} group: {e}")
                return False
    
    # Set permissions for hardware devices
    devices = {
        '/dev/ttyAMA0': '666',  # rw-rw-rw-
        '/dev/gpiomem': '666'   # rw-rw-rw-
    }
    
    for device, perms in devices.items():
        if os.path.exists(device):
            try:
                # Change ownership to root:dialout for serial devices
                if device == '/dev/ttyAMA0':
                    subprocess.run(['sudo', 'chown', 'root:dialout', device], check=True)
                
                # Set permissions
                subprocess.run(['sudo', 'chmod', perms, device], check=True)
                print(f"Set permissions for {device}")
            except subprocess.CalledProcessError as e:
                print(f"Error setting permissions for {device}: {e}")
                return False
                
    return True

def install_system_dependencies():
    """Install required system packages."""
    try:
        # Install required system packages
        subprocess.run(['sudo', 'apt', 'update'], check=True)
        subprocess.run(['sudo', 'apt', 'install', '-y',
            'python3-opencv',
            'python3-picamera2',
            'python3-gpiozero',
            'python3-lgpio',
            'python3-serial'
        ], check=True)
        print("System dependencies installed successfully")
        
        # Get pip path from virtual environment
        venv_python = get_venv_python()
        venv_pip = os.path.join(os.path.dirname(venv_python), 'pip')
        
        # Install Python packages in virtual environment
        print("Installing Python packages in virtual environment...")
        
        # Core dependencies
        subprocess.run([venv_pip, 'install', 'opencv-python'], check=True)
        subprocess.run([venv_pip, 'install', 'pyserial'], check=True)
        subprocess.run([venv_pip, 'install', 'gpiozero'], check=True)
        subprocess.run([venv_pip, 'install', 'picamera2'], check=True)
        
        # Additional required packages
        subprocess.run([venv_pip, 'install', 'tflite-runtime'], check=True)
        subprocess.run([venv_pip, 'install', 'pynmea2'], check=True)
        subprocess.run([venv_pip, 'install', 'numpy'], check=True)
        subprocess.run([venv_pip, 'install', 'flask'], check=True)
        subprocess.run([venv_pip, 'install', 'requests'], check=True)
        
        print("Python packages installed successfully")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return False

def main():
    """Main entry point."""
    print("Setting up waste detection system...")
    
    # Get the virtual environment Python path
    venv_python = get_venv_python()
    print(f"Using Python interpreter: {venv_python}")
    
    # Install system dependencies
    if not install_system_dependencies():
        print("Failed to install system dependencies")
        return 1
    
    # Check and fix permissions
    if not check_and_fix_permissions():
        print("Error setting up permissions")
        return 1
    
    # Run the main application with the virtual environment's Python
    print("Starting waste detection system...")
    try:
        env = os.environ.copy()
        
        # Add PYTHONPATH to include system-wide packages
        python_version = subprocess.check_output([venv_python, '-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'], text=True).strip()
        system_packages = f"/usr/lib/python3/dist-packages:/usr/local/lib/python{python_version}/dist-packages"
        
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = f"{system_packages}:{env['PYTHONPATH']}"
        else:
            env['PYTHONPATH'] = system_packages
            
        if 'VIRTUAL_ENV' in env:
            # Preserve virtual environment variables when running with sudo
            sudo_env = [f"VIRTUAL_ENV={env['VIRTUAL_ENV']}",
                       f"PATH={env['PATH']}",
                       f"PYTHONPATH={env['PYTHONPATH']}"]
            subprocess.run(['sudo', '-E', 'env'] + sudo_env + [venv_python, 'main.py'], check=True, env=env)
        else:
            # No virtual environment, just run with sudo
            subprocess.run(['sudo', venv_python, 'main.py'], check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"Error running main.py: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main()) 