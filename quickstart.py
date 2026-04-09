#!/usr/bin/env python
"""
Quick Start Script for Django Chat Application
Usage: python quickstart.py
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


class ChatAppSetup:
    """Setup and startup handler for chat application"""
    
    def __init__(self):
        self.project_dir = Path(__file__).parent
        self.venv_dir = self.project_dir / 'env'
        self.python_exe = self._get_python_executable()
        self.is_windows = platform.system() == 'Windows'
    
    def _get_python_executable(self):
        """Get Python executable path"""
        if self.is_windows:
            return self.venv_dir / 'Scripts' / 'python.exe'
        else:
            return self.venv_dir / 'bin' / 'python'
    
    def print_banner(self):
        """Print welcome banner"""
        print("""
        ╔════════════════════════════════════════════════════════╗
        ║     🚀 Django Real-Time Chat Application ✨            ║
        ║                                                        ║
        ║  Voice Messaging | Real-Time Updates | Group Chats    ║
        ╚════════════════════════════════════════════════════════╝
        """)
    
    def step_1_create_venv(self):
        """Step 1: Create virtual environment"""
        print("\n📦 Step 1: Creating Virtual Environment...")
        
        if self.venv_dir.exists():
            print(f"✓ Virtual environment already exists at {self.venv_dir}")
            return True
        
        try:
            subprocess.run(
                [sys.executable, '-m', 'venv', str(self.venv_dir)],
                check=True
            )
            print(f"✓ Virtual environment created at {self.venv_dir}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to create virtual environment: {e}")
            return False
    
    def step_2_install_requirements(self):
        """Step 2: Install requirements"""
        print("\n📚 Step 2: Installing Requirements...")
        
        requirements_file = self.project_dir / 'requirements.txt'
        if not requirements_file.exists():
            print(f"✗ requirements.txt not found at {requirements_file}")
            return False
        
        try:
            subprocess.run(
                [str(self.python_exe), '-m', 'pip', 'install', '-r', str(requirements_file)],
                check=True
            )
            print("✓ Requirements installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install requirements: {e}")
            return False
    
    def step_3_run_migrations(self):
        """Step 3: Run Django migrations"""
        print("\n🗄️  Step 3: Running Database Migrations...")
        
        try:
            subprocess.run(
                [str(self.python_exe), 'manage.py', 'migrate'],
                cwd=str(self.project_dir),
                check=True
            )
            print("✓ Database migrations applied successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to run migrations: {e}")
            return False
    
    def step_4_load_sample_data(self):
        """Step 4: Load sample data (optional)"""
        print("\n🌱 Step 4: Loading Sample Data...")
        
        try:
            # Run Python code to load fixtures
            code = """
from chatapp.fixtures import create_sample_data
try:
    create_sample_data()
except Exception as e:
    print(f"Note: {e}")
"""
            subprocess.run(
                [str(self.python_exe), 'manage.py', 'shell', '-c', code],
                cwd=str(self.project_dir),
                check=False  # Don't fail if fixtures already exist
            )
            print("✓ Sample data loaded (or already exists)")
            return True
        except Exception as e:
            print(f"⚠ Could not load sample data: {e}")
            return True  # Don't fail for this step
    
    def step_5_verify_setup(self):
        """Step 5: Verify installation"""
        print("\n✅ Step 5: Verifying Setup...")
        
        checks = {
            'Virtual Environment': self.venv_dir.exists(),
            'Python Executable': self.python_exe.exists(),
            'Management Script': (self.project_dir / 'manage.py').exists(),
            'Django App': (self.project_dir / 'chatapp').is_dir(),
            'Templates': (self.project_dir / 'chatapp' / 'templates').is_dir(),
            'Database': (self.project_dir / 'db.sqlite3').exists(),
        }
        
        all_passed = True
        for check_name, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check_name}")
            if not passed:
                all_passed = False
        
        return all_passed
    
    def step_6_start_server(self):
        """Step 6: Start development server"""
        print("\n🚀 Step 6: Starting Development Server...")
        print("\n" + "="*60)
        print("Server Starting...")
        print("="*60)
        print("\n📍 Access the application at: http://localhost:8000")
        print("📍 Admin panel at: http://localhost:8000/admin")
        print("\n✨ Features:")
        print("   • Voice Messaging (record & send audio)")
        print("   • Real-Time Chat (auto-updates)")
        print("   • Multiple Groups (unique codes)")
        print("   • Message Deletion")
        print("   • Online Users Tracking")
        print("\n💡 Tips:")
        print("   • Open the application in 2+ browser windows")
        print("   • Chat in real-time between windows")
        print("   • Record a voice message using microphone")
        print("   • Messages update automatically")
        print("\n📌 Press Ctrl+C to stop the server")
        print("="*60 + "\n")
        
        try:
            subprocess.run(
                [str(self.python_exe), 'manage.py', 'runserver'],
                cwd=str(self.project_dir)
            )
        except KeyboardInterrupt:
            print("\n\n✓ Server stopped successfully")
            return True
        except Exception as e:
            print(f"\n✗ Failed to start server: {e}")
            return False
    
    def run_setup(self):
        """Run complete setup"""
        self.print_banner()
        
        steps = [
            ("Creating environment", self.step_1_create_venv),
            ("Installing dependencies", self.step_2_install_requirements),
            ("Setting up database", self.step_3_run_migrations),
            ("Loading sample data", self.step_4_load_sample_data),
            ("Verifying installation", self.step_5_verify_setup),
        ]
        
        for step_name, step_func in steps:
            print(f"\n{'='*60}")
            print(f"Working on: {step_name}...")
            print(f"{'='*60}")
            
            if not step_func():
                print(f"\n✗ Setup failed at: {step_name}")
                print("\nTroubleshooting:")
                print("  1. Check that Python 3.9+ is installed")
                print("  2. Ensure pip is available")
                print("  3. Check internet connection for dependencies")
                print("  4. Review error messages above")
                return False
        
        print(f"\n{'='*60}")
        print("✅ Setup Completed Successfully!")
        print(f"{'='*60}")
        
        # Ask to start server
        print("\nWould you like to start the development server now? (y/n)")
        response = input("> ").strip().lower()
        
        if response in ('y', 'yes'):
            self.step_6_start_server()
        else:
            print("\n📝 To start the server manually, run:")
            activate_cmd = (
                f"{self.venv_dir}\\Scripts\\activate"
                if self.is_windows
                else f"source {self.venv_dir}/bin/activate"
            )
            print(f"\n  {activate_cmd}")
            print(f"  python manage.py runserver\n")
        
        return True


def main():
    """Main entry point"""
    setup = ChatAppSetup()
    success = setup.run_setup()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
