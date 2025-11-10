# Configuration

CodeFusion provides simple configuration options to customize exploration behavior for different repositories and use cases.

## Configuration Methods

### 1. Configuration Files

The primary way to configure CodeFusion is through YAML configuration files:

```bash
cf --config /path/to/config.yaml explore /path/to/repo "How does authentication work?"
```

### 2. Command Line Options

Some settings can be overridden via command line:

```bash
cf --verbose explore /path/to/repo "How does X work?"
```

## Configuration Hierarchy

Settings are applied in order of precedence (highest to lowest):

1. **Command line options** (highest priority)
2. **Configuration file** (specified with `--config`)
3. **Default values** (lowest priority)

## Basic Configuration

### Default Configuration

```yaml
# config/default/config.yaml
repo_path: null
output_dir: "./output"

# File filtering
max_file_size: 1048576  # 1MB
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"
  - "venv"
excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
  - ".so"
  - ".dll"
  - ".exe"

# Exploration settings
max_exploration_depth: 5
```

## Configuration Options

### Core Settings

#### `repo_path`
- **Type:** String (optional)
- **Default:** `null`
- **Description:** Default repository path to explore

```yaml
repo_path: "/path/to/default/repo"
```

#### `output_dir`
- **Type:** String
- **Default:** `"./output"`
- **Description:** Directory for output files and cache

```yaml
output_dir: "./my-output"
```

### File Filtering

#### `max_file_size`
- **Type:** Integer
- **Default:** `1048576` (1MB)
- **Description:** Maximum file size in bytes to process

```yaml
max_file_size: 2097152  # 2MB
```

#### `excluded_dirs`
- **Type:** List of strings
- **Default:** `[".git", "__pycache__", "node_modules", ".venv", "venv"]`
- **Description:** Directories to exclude from exploration

```yaml
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"
  - "venv"
  - "dist"
  - "build"
```

#### `excluded_extensions`
- **Type:** List of strings
- **Default:** `[".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe"]`
- **Description:** File extensions to exclude from exploration

```yaml
excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
  - ".so"
  - ".dll"
  - ".exe"
  - ".log"
  - ".tmp"
```

### Exploration Settings

#### `max_exploration_depth`
- **Type:** Integer
- **Default:** `5`
- **Description:** Maximum depth for recursive exploration

```yaml
max_exploration_depth: 10
```

## Configuration Examples

### Basic Repository Configuration

```yaml
# basic-config.yaml
repo_path: "/path/to/my/project"
output_dir: "./codefusion-output"
max_file_size: 1048576  # 1MB
max_exploration_depth: 5
```

### Large Repository Configuration

```yaml
# large-repo-config.yaml
repo_path: "/path/to/large/project"
output_dir: "./large-repo-output"
max_file_size: 2097152  # 2MB
max_exploration_depth: 3

# Exclude additional directories for performance
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"
  - "venv"
  - "dist"
  - "build"
  - "target"
  - "out"
  - "bin"
  - "obj"
  - "vendor"
  - "external"
  - "third_party"

# Exclude more file types
excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
  - ".so"
  - ".dll"
  - ".exe"
  - ".log"
  - ".tmp"
  - ".cache"
  - ".min.js"
  - ".min.css"
  - ".map"
```

### Performance-Optimized Configuration

```yaml
# performance-config.yaml
repo_path: "/path/to/project"
output_dir: "./fast-output"
max_file_size: 524288  # 512KB (smaller files only)
max_exploration_depth: 3

# Minimal exclusions for speed
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"

excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
```

## Using Configuration Files

### Create Configuration

```bash
# Create a new configuration file
cp config/default/config.yaml my-config.yaml

# Edit configuration
nano my-config.yaml

# Use configuration
cf --config my-config.yaml explore /path/to/repo "How does authentication work?"
```

### Configuration Validation

```bash
# Test configuration
cf --config my-config.yaml summary /path/to/repo

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('my-config.yaml'))"
```

## Repository-Specific Configuration

### Project-Specific Settings

```yaml
# web-app-config.yaml
repo_path: "/path/to/web/app"
output_dir: "./web-app-analysis"
max_file_size: 1048576

# Web-specific exclusions
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"
  - "dist"
  - "build"
  - "public"
  - "static"

excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
  - ".min.js"
  - ".min.css"
  - ".map"
  - ".ico"
  - ".png"
  - ".jpg"
  - ".jpeg"
  - ".gif"
  - ".svg"
```

### Language-Specific Settings

```yaml
# python-project-config.yaml
repo_path: "/path/to/python/project"
output_dir: "./python-analysis"
max_file_size: 1048576

# Python-specific exclusions
excluded_dirs:
  - ".git"
  - "__pycache__"
  - ".venv"
  - "venv"
  - "env"
  - ".pytest_cache"
  - ".mypy_cache"
  - "dist"
  - "build"
  - "*.egg-info"

excluded_extensions:
  - ".pyc"
  - ".pyo"
  - ".pyd"
  - ".so"
  - ".dll"
  - ".exe"
```

## Advanced Configuration

### Configuration Templates

Create template configurations for different scenarios:

```bash
# Create templates directory
mkdir -p config/templates

# Create template configurations
cat > config/templates/web-app.yaml << 'EOF'
# Web application configuration
max_file_size: 1048576
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"
  - "dist"
  - "build"
  - "public"
  - "static"
max_exploration_depth: 5
EOF

cat > config/templates/large-repo.yaml << 'EOF'
# Large repository configuration
max_file_size: 2097152
excluded_dirs:
  - ".git"
  - "__pycache__"
  - "node_modules"
  - ".venv"
  - "venv"
  - "dist"
  - "build"
  - "target"
  - "out"
  - "bin"
  - "obj"
  - "vendor"
max_exploration_depth: 3
EOF

# Use templates
cf --config config/templates/web-app.yaml explore /path/to/web/app "How does authentication work?"
```

### Dynamic Configuration

```bash
#!/bin/bash
# generate-config.sh - Generate configuration based on repository type

REPO_PATH="$1"
CONFIG_FILE="generated-config.yaml"

# Detect repository type
if [ -f "$REPO_PATH/package.json" ]; then
    echo "Detected Node.js project"
    cp config/templates/web-app.yaml "$CONFIG_FILE"
elif [ -f "$REPO_PATH/requirements.txt" ] || [ -f "$REPO_PATH/setup.py" ]; then
    echo "Detected Python project"
    cp config/templates/python-project.yaml "$CONFIG_FILE"
else
    echo "Using default configuration"
    cp config/default/config.yaml "$CONFIG_FILE"
fi

# Set repository path
sed -i "s|repo_path: null|repo_path: \"$REPO_PATH\"|" "$CONFIG_FILE"

echo "Generated configuration: $CONFIG_FILE"
```

## Troubleshooting Configuration

### Common Issues

**Invalid YAML syntax:**
```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

**Configuration not found:**
```bash
# Check file exists
ls -la config.yaml

# Use absolute path
cf --config /full/path/to/config.yaml explore /path/to/repo "How does X work?"
```

**Permission issues:**
```bash
# Check file permissions
ls -la config.yaml

# Fix permissions
chmod 644 config.yaml
```

### Debug Configuration

```bash
# Test configuration with verbose output
cf --verbose --config config.yaml summary /path/to/repo

# Validate configuration file
python -c "
import yaml
from cf.config import CfConfig
config = CfConfig.from_file('config.yaml')
config.validate()
print('Configuration is valid')
"
```

## Best Practices

### Configuration Management

1. **Use version control** for configuration files
2. **Create project-specific configurations** for different repositories
3. **Use templates** for common scenarios
4. **Document custom configurations** with comments
5. **Validate configurations** before use

### Performance Optimization

1. **Exclude unnecessary directories** to improve speed
2. **Set appropriate file size limits** for your use case
3. **Use smaller exploration depths** for large repositories
4. **Test configurations** with sample repositories first

### Security Considerations

1. **Never commit sensitive information** in configuration files
2. **Use appropriate file permissions** (644 for config files)
3. **Be careful with excluded directories** - don't exclude important code

## Next Steps

- Learn about [CLI Usage](cli.md)
- See [Usage Examples](examples.md)
- Check the [Installation Guide](../installation/setup.md)