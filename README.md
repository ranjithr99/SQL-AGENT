# SQL AI Agent

A natural language to SQL conversion tool powered by Google's Gemini 2.0 model. This application allows users to query databases using plain English instead of writing SQL code.

## Features

- Translate natural language questions into SQL queries
- Execute SQL queries against your database
- Provide explanations and analysis of generated queries
- Multiple interfaces:
  - CLI tool for command-line operations
  - Web interface for user-friendly access
  - Python library for integration into your applications

## Requirements

- Python 3.8+
- Google AI API key for Gemini 2.0 model
- Database connection (supports any database compatible with SQLAlchemy)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/sql-ai-agent.git
   cd sql-ai-agent
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   # Create a .env file with your Google API key and database connection
   echo "GOOGLE_API_KEY=your_google_api_key" > .env
   echo "DATABASE_URL=your_database_connection_string" >> .env
   ```

## Quick Start

### Setup Sample Database

```bash
python sql_ai_agent_interface.py --setup
```

This creates a sample SQLite database with customers and orders tables.

### Command-Line Interface

Run a single query:
```bash
python sql_ai_agent_interface.py --query "How many customers do we have in each country?"
```

Interactive mode:
```bash
python sql_ai_agent_interface.py --interactive
```

Show database schema:
```bash
python sql_ai_agent_interface.py --schema
```

### Web Interface

Start the web server:
```bash
python sql_ai_web_interface.py
```

Then open your browser and navigate to http://localhost:8080

## Usage Examples

### As a Python Library

```python
from sqlai_agent import SQLAIAgent

# Initialize the agent
agent = SQLAIAgent(
    db_connection_string="sqlite:///your_database.db",
    google_api_key="your_google_api_key"
)

# Process a natural language query
result = agent.process_natural_language("What are the top 5 customers by order value?")

# Print the generated SQL
print(result["query"])

# Print the results
print(result["result"])
```

### CLI Examples

```bash
# Get total orders by country
python sql_ai_agent_interface.py --query "What is the total value of orders from each country?" --format table

# Find latest orders
python sql_ai_agent_interface.py --query "Show me the most recent orders" --format json
```

## Architecture

This project consists of three main components:

1. **Core Agent (`sqlai_agent.py`)**: The main library that handles the conversion of natural language to SQL and executing queries.

2. **Command Line Interface (`sql_ai_agent_interface.py`)**: A CLI tool for interacting with the agent.

3. **Web Interface (`sql_ai_web_interface.py`)**: A Flask web application providing a user-friendly GUI.

## How It Works

1. The user submits a natural language question about the database
2. The Gemini 2.0 model analyzes the question and the database schema
3. The model generates an appropriate SQL query
4. The query is executed against the database
5. Results are formatted and returned to the user
6. (Optionally) The generated SQL is analyzed for safety and performance

## Advanced Configuration

You can customize the agent's behavior by adjusting parameters:

```python
agent = SQLAIAgent(
    db_connection_string="your_connection_string",
    model_name="gemini-2.0-pro",  # Use a more powerful model
    temperature=0.2,  # Adjust creativity (0.0 - 1.0)
    verbose=True  # Enable detailed logging
)
```

## Troubleshooting

### Common Issues

- **API Key Issues**: Ensure your Google API key is valid and has access to Gemini models
- **Database Connection**: Verify your database connection string is correct
- **SQL Extraction Fails**: For complex queries, try simplifying your question or providing more context

### Debug Mode

Enable verbose mode to see detailed logs:

```python
agent = SQLAIAgent(db_connection_string="...", verbose=True)
```

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request