#!/usr/bin/env python3
"""Development setup script for Kargo x Amazon DSP Integration."""
import subprocess
import sys
import os
from pathlib import Path


def run_command(command: str, check: bool = True) -> bool:
    """Run a shell command and return success status."""
    print(f"Running: {command}")
    try:
        result = subprocess.run(command, shell=True, check=check)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Command failed with return code {e.returncode}")
        return False


def check_prerequisites():
    """Check if required tools are installed."""
    print("Checking prerequisites...")
    
    required_tools = {
        "python3": "Python 3.11+",
        "docker": "Docker",
        "docker-compose": "Docker Compose",
        "git": "Git"
    }
    
    missing_tools = []
    for tool, description in required_tools.items():
        if not run_command(f"which {tool}", check=False):
            missing_tools.append(f"{tool} ({description})")
    
    if missing_tools:
        print("Missing required tools:")
        for tool in missing_tools:
            print(f"  - {tool}")
        return False
    
    print("All prerequisites are available ✓")
    return True


def setup_python_environment():
    """Set up Python virtual environment and install dependencies."""
    print("\nSetting up Python environment...")
    
    # Create virtual environment if it doesn't exist
    if not Path("venv").exists():
        if not run_command("python3 -m venv venv"):
            return False
    
    # Activate virtual environment and install dependencies
    pip_cmd = "venv/bin/pip" if os.name != "nt" else "venv\\Scripts\\pip"
    
    commands = [
        f"{pip_cmd} install --upgrade pip",
        f"{pip_cmd} install -r requirements.txt",
    ]
    
    for command in commands:
        if not run_command(command):
            return False
    
    print("Python environment setup complete ✓")
    return True


def setup_pre_commit():
    """Set up pre-commit hooks."""
    print("\nSetting up pre-commit hooks...")
    
    python_cmd = "venv/bin/python" if os.name != "nt" else "venv\\Scripts\\python"
    
    commands = [
        f"{python_cmd} -m pip install pre-commit",
        "venv/bin/pre-commit install" if os.name != "nt" else "venv\\Scripts\\pre-commit install"
    ]
    
    for command in commands:
        if not run_command(command):
            return False
    
    print("Pre-commit hooks setup complete ✓")
    return True


def setup_docker_environment():
    """Set up Docker environment."""
    print("\nSetting up Docker environment...")
    
    # Build Docker images
    if not run_command("docker-compose -f docker/docker-compose.yml build"):
        return False
    
    print("Docker environment setup complete ✓")
    return True


def create_env_file():
    """Create environment file from template."""
    print("\nCreating environment configuration...")
    
    env_content = """# Kargo x Amazon DSP Integration Environment Configuration

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/kargo_dsp
DATABASE_ECHO=false

# Redis
REDIS_URL=redis://localhost:6379/0

# Application
ENVIRONMENT=development
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-here

# Amazon DSP API (configure when available)
# AMAZON_DSP_CLIENT_ID=your-client-id
# AMAZON_DSP_CLIENT_SECRET=your-client-secret
# AMAZON_DSP_BASE_URL=https://api.amazon-adsystem.com

# Kargo API (configure when available)
# KARGO_API_KEY=your-api-key
# KARGO_BASE_URL=https://snippet.kargo.com

# Monitoring
PROMETHEUS_ENABLED=true
METRICS_PORT=8001

# Testing
TEST_DATABASE_URL=sqlite+aiosqlite:///:memory:
"""
    
    env_file = Path(".env")
    if not env_file.exists():
        env_file.write_text(env_content)
        print("Environment file created ✓")
    else:
        print("Environment file already exists ✓")
    
    return True


def run_initial_tests():
    """Run initial tests to verify setup."""
    print("\nRunning initial tests...")
    
    python_cmd = "venv/bin/python" if os.name != "nt" else "venv\\Scripts\\python"
    
    # Run linting
    print("Running linting...")
    if not run_command(f"{python_cmd} -m ruff check app/"):
        print("Linting failed ❌")
        return False
    
    # Run type checking
    print("Running type checking...")
    if not run_command(f"{python_cmd} -m mypy app/", check=False):
        print("Type checking has warnings (this is expected initially)")
    
    # Run basic tests
    print("Running tests...")
    if not run_command(f"{python_cmd} -m pytest app/tests/test_health.py -v"):
        print("Basic tests failed ❌")
        return False
    
    print("Initial tests passed ✓")
    return True


def main():
    """Main setup function."""
    print("🚀 Kargo x Amazon DSP Integration - Development Setup")
    print("=" * 60)
    
    setup_steps = [
        ("Prerequisites", check_prerequisites),
        ("Python Environment", setup_python_environment),
        ("Pre-commit Hooks", setup_pre_commit),
        ("Environment File", create_env_file),
        ("Docker Environment", setup_docker_environment),
        ("Initial Tests", run_initial_tests),
    ]
    
    for step_name, step_func in setup_steps:
        print(f"\n📋 {step_name}")
        print("-" * 40)
        
        if not step_func():
            print(f"\n❌ Setup failed at step: {step_name}")
            sys.exit(1)
    
    print("\n" + "=" * 60)
    print("🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Start the development environment:")
    print("   docker-compose -f docker/docker-compose.yml up")
    print("\n2. Visit the API documentation:")
    print("   http://localhost:8000/docs")
    print("\n3. Check health endpoint:")
    print("   http://localhost:8000/health")
    print("\n4. Run tests:")
    print("   venv/bin/python -m pytest")
    print("\n5. Start developing! 🚀")


if __name__ == "__main__":
    main()