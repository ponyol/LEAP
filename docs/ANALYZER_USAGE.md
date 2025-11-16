# LEAP Analyzer Usage Guide

The LEAP Analyzer uses LLMs to analyze log statements and generate human-readable explanations.

## Installation

```bash
# Install base LEAP
pip install -e .

# Install with all analyzer providers
pip install -e ".[all]"

# Or install specific providers
pip install -e ".[analyzer]"  # All providers
pip install anthropic          # Just Anthropic
pip install boto3             # Just AWS Bedrock
pip install httpx             # Just Ollama/LMStudio
```

## Quick Start

### 1. Extract logs from your codebase

```bash
leap extract /path/to/your/repo -o raw_logs.json
```

### 2. Analyze with LLM

#### Using Anthropic Claude (recommended)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
leap analyze raw_logs.json -o analyzed_logs.json
```

#### Using Ollama (local, free)

```bash
# Start Ollama
ollama serve

# Pull a model
ollama pull llama3:8b

# Analyze
leap analyze raw_logs.json --provider ollama --model llama3:8b
```

#### Using AWS Bedrock

```bash
# Configure AWS credentials
export AWS_REGION="us-east-1"
export AWS_PROFILE="my-profile"

# Analyze
leap analyze raw_logs.json \
  --provider bedrock \
  --model anthropic.claude-3-5-sonnet-20241022-v2:0
```

#### Using LM Studio (local, GUI)

```bash
# Start LM Studio and enable server
# Load a model in LM Studio

# Analyze
leap analyze raw_logs.json --provider lmstudio --model local-model
```

## Advanced Usage

### Concurrency Control

```bash
# Increase parallelism for faster processing
leap analyze raw_logs.json -c 20

# Decrease for rate-limited APIs
leap analyze raw_logs.json -c 5
```

### Language Selection

```bash
# Russian language analysis
leap analyze raw_logs.json -l ru

# English (default)
leap analyze raw_logs.json -l en
```

### Custom Prompts

```bash
# Use your own prompt template
leap analyze raw_logs.json --analysis-prompt my_custom_prompt.txt
```

Example custom prompt (`my_custom_prompt.txt`):
```
You are analyzing a log statement.

Language: {language}
Log: {log_template}
Context:
{code_context}

Respond with JSON:
{{
  "analysis": "Brief explanation",
  "severity": "INFO",
  "suggested_action": null
}}
```

### Disable Caching

```bash
# Disable deduplication cache (analyze all entries, even duplicates)
leap analyze raw_logs.json --no-cache
```

## Output Format

The `analyzed_logs.json` contains:

```json
{
  "analyzed_logs": [
    {
      "log_template": "User login failed",
      "analysis": "This log is emitted when user.authenticate() returns false, indicating invalid credentials were provided during login attempt",
      "severity": "ERROR",
      "suggested_action": "Check user credentials in database and verify authentication service is operational",
      "language": "python",
      "source_file": "src/auth.py:42"
    }
  ],
  "metadata": {
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20241022",
    "language": "en",
    "total_entries": 1268,
    "successful": 1250,
    "failed": 18,
    "cache_stats": {
      "hits": 350,
      "misses": 918,
      "size": 918,
      "hit_rate": 27.6
    }
  }
}
```

## Provider-Specific Configuration

### Anthropic Claude

**Environment Variables:**
- `ANTHROPIC_API_KEY` (required)

**Recommended Models:**
- `claude-3-5-sonnet-20241022` (best quality/speed tradeoff)
- `claude-3-opus-20240229` (highest quality)
- `claude-3-haiku-20240307` (fastest, cheapest)

**Cost Estimate:**
- ~$5 per 1000 logs (with Sonnet 3.5)

### AWS Bedrock

**Environment Variables:**
- `AWS_REGION` (default: us-east-1)
- `AWS_PROFILE` (optional)

**Recommended Models:**
- `anthropic.claude-3-5-sonnet-20241022-v2:0`
- `anthropic.claude-3-opus-20240229-v1:0`

**Prerequisites:**
- AWS credentials configured
- Bedrock access enabled in your AWS account
- Model access granted in Bedrock console

### Ollama (Local)

**Prerequisites:**
- Install Ollama: https://ollama.ai
- Pull a model: `ollama pull llama3:8b`

**Environment Variables:**
- `OLLAMA_API_BASE` (default: http://localhost:11434)

**Recommended Models:**
- `llama3:8b` - Good general purpose
- `codellama:7b` - Specialized for code
- `mistral:7b` - Fast and capable

**Note:** Local models are free but may have lower quality than cloud models.

### LM Studio (Local)

**Prerequisites:**
- Install LM Studio: https://lmstudio.ai
- Download and load a model in LM Studio
- Enable "Local Server" in LM Studio settings

**Environment Variables:**
- `LMSTUDIO_API_BASE` (default: http://localhost:1234)

## Performance Tips

1. **Increase Concurrency:** Cloud providers can handle high concurrency (20-50)
2. **Use Caching:** Enabled by default, saves ~30% on duplicate logs
3. **Choose Right Model:** Balance quality vs. cost/speed
4. **Local for Development:** Use Ollama/LMStudio for testing prompts

## Troubleshooting

### "Provider failed health check"

**For Anthropic:**
```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Test with curl
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-haiku-20240307","max_tokens":10,"messages":[{"role":"user","content":"test"}]}'
```

**For Ollama:**
```bash
# Check if Ollama is running
curl http://localhost:11434/

# List available models
ollama list
```

### "Analysis failed" for many entries

- Check your prompt template is valid
- Ensure model has enough context (some models have token limits)
- Try a more capable model

### Rate Limit Errors

```bash
# Decrease concurrency
leap analyze raw_logs.json -c 5

# Increase timeout
leap analyze raw_logs.json --timeout 120
```

## Next Steps

After analysis, you can:
1. Use `analyzed_logs.json` to build a RAG index (Component 3)
2. Import into your observability platform
3. Generate documentation from the analysis
4. Identify high-severity logs for alerting
