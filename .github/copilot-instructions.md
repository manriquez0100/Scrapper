# Amazon Product Scraper - Copilot Instructions

## Project Overview
This workspace contains a Python-based Amazon product scraper that extracts product information from Amazon pages.

## Project Structure
- `scraper/` - Main scraper package with core functionality
- `demo.py` - Demonstration script showing scraper capabilities  
- `main.py` - Interactive scraper interface
- `requirements.txt` - Python dependencies
- `.venv/` - Python virtual environment (pre-configured)

## Key Features
- Extract product titles, prices, ratings, reviews, availability
- Search products by keywords
- Export data to JSON format
- Anti-detection measures (delays, headers, user agents)
- Comprehensive error handling

## Development Guidelines
- Virtual environment is already configured in `.venv/`
- Dependencies are installed via `pip install -r requirements.txt`
- Run demo with `python demo.py`
- Run interactive mode with `python main.py`
- Use VS Code tasks for common operations

## Code Style
- Follow PEP 8 Python style guidelines
- Use descriptive variable names
- Add docstrings to functions and classes
- Handle exceptions gracefully
- Respect rate limits and Amazon's robots.txt

## Testing
- Use `demo.py` to verify functionality
- Test with various Amazon product URLs
- Check connectivity before scraping
- Validate extracted data formats

## Legal Considerations
- Respect Amazon's Terms of Service
- Use appropriate delays between requests
- This tool is for educational/personal use only
- Consider robots.txt compliance
