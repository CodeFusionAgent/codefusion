# Quick Start

Get up and running with CodeFusion in minutes.

## Prerequisites

- Python 3.10 or higher
- Git

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd codefusion

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install CodeFusion
pip install -e .

# Verify installation
cf --help
```

## First Exploration

```bash
# Explore a repository
cf explore /path/to/your/repo "How does authentication work?"

# Continue exploration
cf continue /path/to/your/repo "How are sessions managed?" --previous "How does authentication work?"

# View exploration summary
cf summary /path/to/your/repo
```

## Example Questions

Try these example questions:

- "How does authentication work?"
- "What are the main API endpoints?"
- "How is data stored and retrieved?"
- "What testing frameworks are used?"
- "How is the application configured?"

## Next Steps

- Read the [CLI Usage Guide](../usage/cli.md)
- Learn about [Configuration](../usage/configuration.md)
- Check the [Installation Guide](setup.md) for detailed setup

## Need Help?

- Use `cf --help` for command help
- Use `cf --verbose` for detailed output
- Check the [documentation](../index.md) for more information