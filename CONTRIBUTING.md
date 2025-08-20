# Contributing to Kargo Amazon DSP Integration

Thank you for considering contributing to the Kargo Amazon DSP Integration project! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

This project follows a Code of Conduct to ensure a welcoming environment for all contributors. By participating, you are expected to uphold this code.

### Our Standards

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git
- GitHub account

### Development Setup

1. **Fork the Repository**
   ```bash
   # Fork on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/kargo-amazon-dsp-integration.git
   cd kargo-amazon-dsp-integration
   ```

2. **Set Up Remote**
   ```bash
   git remote add upstream https://github.com/BNYEDAGAWD/kargo-amazon-dsp-integration.git
   ```

3. **Create Development Environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Set up pre-commit hooks
   pre-commit install
   ```

4. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your development configuration
   ```

5. **Start Services**
   ```bash
   # Start with Docker Compose
   docker-compose up -d
   
   # Or run locally
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Development Workflow

### Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/feature-name` - Feature branches
- `bugfix/issue-description` - Bug fix branches
- `hotfix/urgent-fix` - Critical production fixes

### Working on Features

1. **Create Feature Branch**
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write code following our standards
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Changes**
   ```bash
   # Run tests
   pytest
   
   # Run linting
   ruff check .
   black --check .
   
   # Run type checking
   mypy app/
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

### Commit Message Format

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or modifying tests
- `chore`: Build process or auxiliary tool changes

**Examples:**
```bash
feat(api): add campaign creation endpoint
fix(database): resolve connection pool timeout issue
docs: update deployment guide
test(creative): add unit tests for image processing
```

## Code Standards

### Python Style Guide

- Follow [PEP 8](https://pep8.org/)
- Use [Black](https://black.readthedocs.io/) for code formatting
- Use [isort](https://isort.readthedocs.io/) for import sorting
- Use [Ruff](https://beta.ruff.rs/) for linting
- Use [mypy](https://mypy.readthedocs.io/) for type checking

### Code Quality Tools

```bash
# Format code
black .
isort .

# Lint code
ruff check .

# Type check
mypy app/

# Run all checks
pre-commit run --all-files
```

### Code Organization

- **Functions**: Use descriptive names and include type hints
- **Classes**: Follow PascalCase naming convention
- **Variables**: Use snake_case naming convention
- **Constants**: Use UPPER_CASE naming convention
- **Modules**: Use snake_case naming convention

### Documentation Strings

Use [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) docstrings:

```python
def create_campaign(name: str, budget: float) -> Campaign:
    """Create a new advertising campaign.
    
    Args:
        name: The campaign name
        budget: The campaign budget in USD
        
    Returns:
        The created campaign object
        
    Raises:
        ValidationError: If campaign data is invalid
        DatabaseError: If database operation fails
    """
    pass
```

## Testing Guidelines

### Test Structure

```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
├── fixtures/       # Test fixtures and data
└── conftest.py     # Pytest configuration
```

### Writing Tests

1. **Unit Tests**
   - Test individual functions/methods in isolation
   - Mock external dependencies
   - Aim for high code coverage

2. **Integration Tests**
   - Test component interactions
   - Use test databases
   - Test API endpoints end-to-end

3. **Test Naming**
   ```python
   def test_create_campaign_with_valid_data():
       """Test that campaign creation succeeds with valid data."""
       pass
   
   def test_create_campaign_raises_error_for_invalid_budget():
       """Test that campaign creation raises error for negative budget."""
       pass
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_campaigns.py

# Run tests with verbose output
pytest -v

# Run integration tests only
pytest tests/integration/
```

## Documentation

### Types of Documentation

1. **Code Documentation**
   - Inline comments for complex logic
   - Docstrings for all public functions/classes
   - Type hints for all function parameters and returns

2. **API Documentation**
   - FastAPI automatically generates OpenAPI docs
   - Add descriptions to endpoints and models
   - Include example requests/responses

3. **User Documentation**
   - README.md for project overview
   - docs/ directory for detailed guides
   - Deployment and configuration instructions

### Writing Documentation

- Use clear, concise language
- Include practical examples
- Keep documentation up-to-date with code changes
- Use Markdown formatting consistently

## Submitting Changes

### Pull Request Process

1. **Before Submitting**
   - Ensure all tests pass
   - Update documentation
   - Rebase on latest main branch
   - Squash commits if necessary

2. **Create Pull Request**
   - Use descriptive title and description
   - Link related issues
   - Fill out PR template completely
   - Request appropriate reviewers

3. **Review Process**
   - Address reviewer feedback
   - Make requested changes
   - Keep discussions respectful and constructive

4. **After Approval**
   - Squash and merge (preferred method)
   - Delete feature branch

### Pull Request Checklist

- [ ] Tests added/updated for changes
- [ ] Documentation updated
- [ ] Code follows style guidelines
- [ ] All CI checks passing
- [ ] Breaking changes documented
- [ ] Database migrations included (if applicable)

## Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- MAJOR.MINOR.PATCH (e.g., 1.2.3)
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes (backward compatible)

### Release Steps

1. Create release branch from main
2. Update version numbers
3. Update CHANGELOG.md
4. Create release PR
5. After merge, tag release
6. Deploy to production

## Getting Help

### Resources

- **Documentation**: Check the `/docs` directory
- **API Docs**: http://localhost:8000/docs (when running locally)
- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share ideas

### Contact

- Create an issue for bugs or feature requests
- Use GitHub Discussions for questions
- Check existing issues before creating new ones

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- GitHub contributor insights

Thank you for contributing to the Kargo Amazon DSP Integration project! 🚀