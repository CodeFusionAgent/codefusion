# Performance Guide

This document covers performance optimization techniques, monitoring, and best practices for CodeFusion development.

## Performance Overview

CodeFusion is designed to handle large codebases efficiently through various optimization strategies:

- **Batch Processing**: Configurable batch sizes for memory management
- **Parallel Processing**: Multi-threaded file processing
- **Caching**: Multiple layers of caching for faster responses
- **Incremental Processing**: Avoid reprocessing unchanged files
- **Memory Management**: Configurable limits and cleanup

## Performance Monitoring

### Built-in Metrics

CodeFusion tracks several performance metrics:

```python
# Example metrics from cf stats
{
    "indexing_time": 45.2,           # seconds
    "files_processed": 1247,
    "entities_extracted": 2845,
    "average_file_size": 2.4,        # KB
    "memory_usage": 156,             # MB
    "cache_hit_rate": 0.78
}
```

### Monitoring Commands

```bash
# Basic performance stats
cf stats

# Detailed timing information
cf --verbose index /path/to/repo

# Memory usage monitoring
time cf index /path/to/large/repo

# With detailed system monitoring
/usr/bin/time -v cf index /path/to/repo
```

### Performance Profiling

Enable debug mode for detailed performance information:

```bash
export CF_DEBUG=1
cf index /path/to/repo
```

## Optimization Strategies

### 1. Configuration Tuning

#### Memory-Optimized Configuration

```yaml
# config/memory-optimized.yaml
kb_type: "text"                    # Minimal memory usage
max_file_size: 524288              # 512KB limit
batch_size: 25                     # Small batches
max_workers: 2                     # Reduce parallelism
cache_enabled: false               # Disable caching

excluded_dirs:
  - ".git"
  - "node_modules"
  - "vendor"
  - "build"
  - "dist"
  - "__pycache__"
  - ".pytest_cache"
  - ".mypy_cache"
  - "coverage"
```

#### Speed-Optimized Configuration

```yaml
# config/speed-optimized.yaml
kb_type: "vector"                  # Fast search
max_file_size: 2097152            # 2MB limit
batch_size: 200                   # Large batches
max_workers: 8                    # High parallelism
cache_enabled: true               # Enable caching
exploration_strategy: "react"      # Fastest strategy
max_exploration_depth: 3          # Shallow exploration

excluded_dirs:
  - ".git"
  - "node_modules"
  - "__pycache__"
```

#### Large Repository Configuration

```yaml
# config/large-repo.yaml
kb_type: "neo4j"                  # Best for complex relationships
max_file_size: 1048576            # 1MB limit
batch_size: 100                   # Balanced batching
max_workers: 6                    # Moderate parallelism
exploration_strategy: "sense_act"  # Best for large codebases
max_exploration_depth: 15         # Deep exploration

# Aggressive filtering
excluded_dirs:
  - ".git"
  - "node_modules"
  - "vendor"
  - "third_party"
  - "external"
  - "deps"
  - "build"
  - "dist"
  - "out"
  - "target"
  - "bin"
  - "obj"
  - "logs"
  - "tmp"
  - "temp"
  - "cache"
  - ".cache"
  - "__pycache__"
  - ".pytest_cache"
  - ".mypy_cache"
  - "coverage"
  - ".coverage"
  - "htmlcov"
```

### 2. File Filtering Optimization

#### Effective Directory Exclusions

```yaml
# High-impact exclusions (most files)
excluded_dirs:
  - "node_modules"        # JavaScript dependencies
  - "__pycache__"         # Python bytecode
  - ".git"                # Version control
  - "vendor"              # Package dependencies
  - "build"               # Build artifacts
  - "dist"                # Distribution files

# Additional exclusions for large projects
excluded_dirs:
  - ".pytest_cache"
  - ".mypy_cache"
  - ".tox"
  - "coverage"
  - "htmlcov"
  - ".nyc_output"
  - "logs"
  - "tmp"
  - "temp"
```

#### File Extension Filtering

```yaml
# Performance-critical exclusions
excluded_extensions:
  - ".pyc"              # Python bytecode
  - ".pyo"              # Python optimized
  - ".pyd"              # Python extension
  - ".so"               # Shared libraries
  - ".dll"              # Windows libraries
  - ".exe"              # Executables
  - ".map"              # Source maps
  - ".min.js"           # Minified JavaScript
  - ".min.css"          # Minified CSS
  - ".bundle.js"        # Bundled JavaScript
  - ".chunk.js"         # Code chunks
  - ".log"              # Log files
  - ".tmp"              # Temporary files
```

### 3. Vector Database Optimization

#### Embedding Model Selection

```yaml
# Fast, good quality (recommended)
embedding_model: "all-MiniLM-L6-v2"     # 384 dimensions

# Higher quality, slower
embedding_model: "all-mpnet-base-v2"     # 768 dimensions

# Optimized for code
embedding_model: "BAAI/bge-small-en-v1.5"  # 384 dimensions, code-optimized
```

### 4. LLM Provider Optimization

#### Request Optimization

```yaml
llm_settings:
  temperature: 0.0            # Deterministic responses
  max_tokens: 2048           # Reasonable limit
  timeout: 30                # Request timeout
  retry_attempts: 3          # Retry failed requests
```

#### Provider Selection

```yaml
# For speed
llm_model: "gpt-3.5-turbo"

# For quality
llm_model: "gpt-4"

# For cost optimization
llm_model: "gpt-3.5-turbo"
max_tokens: 1024
temperature: 0.0
```

## Performance Benchmarks

### Repository Size Guidelines

| Repository Size | Recommended Config | Expected Time | Memory Usage |
|----------------|-------------------|---------------|--------------|
| Small (< 1K files) | Default | 5-15 seconds | 50-100 MB |
| Medium (1-10K files) | Speed-optimized | 30-120 seconds | 100-300 MB |
| Large (10-100K files) | Large-repo | 5-30 minutes | 500MB-2GB |
| Very Large (100K+ files) | Custom tuning | 30+ minutes | 2GB+ |

### Performance by File Type

| File Type | Processing Speed | Memory Impact | Notes |
|-----------|-----------------|---------------|--------|
| Python (.py) | Fast | Low | Good AST support |
| JavaScript (.js) | Fast | Low | Standard processing |
| TypeScript (.ts) | Medium | Medium | Type analysis |
| Java (.java) | Medium | Medium | Class hierarchy |
| C++ (.cpp/.h) | Slow | High | Complex parsing |
| JSON (.json) | Very Fast | Very Low | Simple structure |
| Markdown (.md) | Fast | Low | Text processing |

## Memory Management

### Memory Optimization Techniques

1. **Streaming Processing**: Process files one at a time for large repositories
2. **Garbage Collection**: Explicit cleanup after batch processing
3. **Memory Limits**: Set maximum memory thresholds
4. **Cache Management**: LRU cache with size limits

### Memory Configuration

```yaml
memory_management:
  max_memory_mb: 2048         # 2GB limit
  gc_threshold: 0.8           # Trigger cleanup at 80%
  cache_size: 1000           # Maximum cached items
  batch_size: 50             # Reduce if memory constrained
```

## Troubleshooting Performance Issues

### Common Performance Problems

#### Slow Indexing

**Symptoms**: Indexing takes much longer than expected

**Solutions**:
1. Check excluded directories and extensions
2. Reduce max_file_size
3. Increase batch_size (if enough memory)
4. Use faster embedding model
5. Enable parallel processing

#### High Memory Usage

**Symptoms**: Process uses excessive memory or crashes

**Solutions**:
1. Reduce batch_size
2. Decrease max_workers
3. Add more excluded directories
4. Lower max_file_size
5. Use text-based knowledge base

#### Slow Queries

**Symptoms**: Query responses are slow

**Solutions**:
1. Enable caching
2. Use vector database for semantic search
3. Reduce exploration depth
4. Optimize configuration
5. Use faster LLM model

### Diagnostic Commands

```bash
# Check system resources
htop
free -h
df -h

# Monitor CodeFusion process
ps aux | grep cf

# Check disk I/O
iotop
```

### Performance Debugging

```bash
# Enable detailed logging
export CF_DEBUG=1

# Run with profiling
python -m cProfile -o profile.stats -m cf index /path/to/repo

# Analyze profile
python -c "
import pstats
stats = pstats.Stats('profile.stats')
stats.sort_stats('cumulative')
stats.print_stats(20)
"
```

## Best Practices

### Development Performance

1. **Use small test repositories** during development
2. **Enable caching** for faster iteration
3. **Profile regularly** to catch performance regressions
4. **Test with different repository sizes** before release
5. **Monitor memory usage** in long-running processes

### Production Performance

1. **Tune configuration** for your specific use case
2. **Monitor resource usage** in production
3. **Set appropriate limits** to prevent resource exhaustion
4. **Use incremental processing** for large repositories
5. **Implement circuit breakers** for external API calls

### Configuration Guidelines

```yaml
# Production-ready configuration template
production_config:
  # Resource limits
  max_file_size: 1048576        # 1MB
  batch_size: 100               # Balanced
  max_workers: 4                # CPU cores / 2
  
  # Memory management
  cache_enabled: true
  cache_size: 2000
  
  # Timeouts
  llm_timeout: 60
  query_timeout: 300
  
  # Aggressive filtering
  excluded_dirs:
    - ".git"
    - "node_modules"
    - "__pycache__"
    - "build"
    - "dist"
    - "vendor"
    - "logs"
    - "tmp"
    - "cache"
  
  # Performance monitoring
  enable_metrics: true
  metrics_interval: 60
```

## Next Steps

- Review [architecture documentation](architecture.md) for system design
- Check [testing guide](testing.md) for comprehensive testing strategies
- See [configuration reference](../config/reference.md) for detailed options