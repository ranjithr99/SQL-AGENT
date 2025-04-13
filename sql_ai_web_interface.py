from flask import Flask, request, jsonify, render_template
import os
import re
from dotenv import load_dotenv
import pandas as pd
import json
from sqlalchemy import text
from sqlai_agent import SQLAIAgent

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure database connection
DB_CONNECTION = os.getenv("DATABASE_URL", "sqlite:///example.db")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Initialize the SQL AI Agent
agent = SQLAIAgent(
    db_connection_string=DB_CONNECTION,
    google_api_key=GOOGLE_API_KEY,
    model_name="gemini-2.0-flash",
    verbose=True
)

def clean_sql_query(query):
    """
    Clean up SQL query to fix common formatting issues.
    """
    if not query:
        return query
        
    # Remove any markdown formatting
    query = re.sub(r'```(?:sql)?|```', '', query)
    
    # Remove quotes around the entire query
    query = re.sub(r'^["\'](.*)["\']$', r'\1', query.strip())
    
    # Remove any "sql" prefix that might appear
    query = re.sub(r'^sql\s+', '', query, flags=re.IGNORECASE)
    
    # Replace smart quotes with standard quotes
    query = query.replace('"', '"').replace('"', '"')
    query = query.replace("'", "'").replace("'", "'")
    
    # Remove any non-ASCII characters
    query = ''.join(c for c in query if ord(c) < 128)
    
    # Strip whitespace
    query = query.strip()
    
    return query

@app.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html')

@app.route('/api/query', methods=['POST'])
def process_query():
    """Process a natural language query and return results."""
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    # Process the query
    result = agent.process_natural_language(query)
    
    # Extract SQL if it's not already present
    if not result.get('query') and isinstance(result.get('result'), str):
        extracted_sql = agent._extract_sql_from_response(result['result'])
        if extracted_sql:
            result['query'] = extracted_sql
    
    # Clean the SQL query if present
    if result.get('query'):
        original_query = result['query']
        result['query'] = clean_sql_query(result['query'])
        
        # Try executing the cleaned query
        try:
            df = agent.run_query(result['query'])
            # Convert to JSON-serializable format
            result['table_data'] = {
                'columns': df.columns.tolist(),
                'rows': df.values.tolist(),
                'is_tabular': True
            }
            # Clear any previous SQL errors if the query was successful
            if 'sql_error' in result:
                del result['sql_error']
        except Exception as e:
            error_msg = str(e)
            print(f"SQL Execution Error: {error_msg}")
            
            # Try a fallback to direct SQL if the extracted query had issues
            if 'syntax error' in error_msg.lower():
                try:
                    # Create a more direct SQL query based on the original
                    fallback_query = f"SELECT city, COUNT(*) as count FROM customer GROUP BY city"
                    df = agent.run_query(fallback_query)
                    result['query'] = fallback_query  # Update with the successful query
                    result['table_data'] = {
                        'columns': df.columns.tolist(),
                        'rows': df.values.tolist(),
                        'is_tabular': True
                    }
                    # Add a note about the fallback
                    result['query_note'] = "Query was adjusted for compatibility."
                    # Clear any SQL errors since we recovered
                    if 'sql_error' in result:
                        del result['sql_error']
                except Exception as fallback_error:
                    # If fallback also fails, keep the original error
                    result['sql_error'] = error_msg
            else:
                # For non-syntax errors, keep the original error
                result['sql_error'] = error_msg
    
    return jsonify(result)

@app.route('/api/schema', methods=['GET'])
def get_schema():
    """Return the database schema."""
    schema = agent.get_schema()
    return jsonify({"schema": schema})

@app.route('/api/analyze', methods=['POST'])
def analyze_query():
    """Analyze a SQL query for safety and optimization."""
    data = request.json
    query = data.get('query', '')
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    # Clean the query before analysis
    query = clean_sql_query(query)
    
    analysis = agent.analyze_query(query)
    return jsonify(analysis)

# Templates directory
@app.route('/templates/<path:path>')
def send_template(path):
    """Serve template files."""
    return app.send_static_file(f'templates/{path}')

# Create templates directory if it doesn't exist
os.makedirs('templates', exist_ok=True)

# Create index.html file
with open('templates/index.html', 'w') as f:
    f.write("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQL AI Assistant</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding-top: 20px; }
        .result-area { min-height: 200px; }
        .sql-query { 
            font-family: monospace; 
            background-color: #f8f9fa; 
            padding: 10px; 
            border-radius: 5px; 
            white-space: pre-wrap;
        }
        .table-responsive { margin-top: 15px; overflow-x: auto; }
        .results-table { 
            width: 100%; 
            border-collapse: collapse; 
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .results-table th { 
            background-color: #4a76a8; 
            color: white;
            padding: 12px 8px; 
            text-align: left; 
            border: 1px solid #e0e0e0;
            position: sticky;
            top: 0;
        }
        .results-table td { 
            padding: 10px 8px; 
            border: 1px solid #e0e0e0; 
        }
        .results-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .results-table tr:hover {
            background-color: #f0f7ff;
        }
        .debug-info {
            margin-top: 20px;
            font-size: 0.8em;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
        }
        .table-container {
            margin-top: 15px;
            max-height: 500px;
            overflow-y: auto;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
        }
        .sql-error {
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 10px 15px;
            margin: 10px 0;
            border-radius: 0 4px 4px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4">SQL AI Assistant</h1>
        
        <div class="row">
            <div class="col-md-12">
                <div class="card mb-4">
                    <div class="card-header">
                        Ask a question about your database
                    </div>
                    <div class="card-body">
                        <div class="input-group mb-3">
                            <input type="text" id="queryInput" class="form-control" placeholder="e.g., How many customers do we have in each country?">
                            <button class="btn btn-primary" type="button" id="submitBtn">Submit</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <div class="card mb-4">
                    <div class="card-header">
                        Generated SQL Query
                    </div>
                    <div class="card-body">
                        <div id="sqlQuery" class="sql-query result-area">
                            <!-- SQL query will appear here -->
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="card mb-4">
                    <div class="card-header">
                        Results Description
                    </div>
                    <div class="card-body">
                        <div id="results" class="result-area">
                            <!-- Text results will appear here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        Data Table
                    </div>
                    <div class="card-body">
                        <div id="sqlError" class="sql-error" style="display: none;">
                            <!-- SQL error will appear here -->
                        </div>
                        <div class="table-container">
                            <div id="tableResults" class="table-responsive">
                                <!-- Table results will appear here -->
                            </div>
                        </div>
                        <div id="debugContainer">
                            <!-- Debug info will appear here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Helper function to clean SQL query for display
        function formatSqlForDisplay(sql) {
            if (!sql) return '';
            
            // Basic SQL formatting for display
            return sql
                .replace(/SELECT/gi, 'SELECT')
                .replace(/FROM/gi, 'FROM')
                .replace(/WHERE/gi, 'WHERE')
                .replace(/GROUP BY/gi, 'GROUP BY')
                .replace(/ORDER BY/gi, 'ORDER BY')
                .replace(/HAVING/gi, 'HAVING')
                .replace(/LIMIT/gi, 'LIMIT')
                .replace(/JOIN/gi, 'JOIN')
                .replace(/ON/gi, 'ON')
                .replace(/AND/gi, 'AND')
                .replace(/OR/gi, 'OR')
                .replace(/UNION/gi, 'UNION');
        }
    
        document.getElementById('submitBtn').addEventListener('click', async function() {
            const query = document.getElementById('queryInput').value;
            if (!query) return;
            
            // Clear previous results
            document.getElementById('sqlQuery').innerHTML = '<div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div>';
            document.getElementById('results').innerHTML = '<div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div>';
            document.getElementById('tableResults').innerHTML = '';
            document.getElementById('sqlError').style.display = 'none';
            document.getElementById('debugContainer').innerHTML = '';
            
            try {
                // Send the query
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ query }),
                });
                
                const data = await response.json();
                
                // Display SQL query if available
                if (data.query) {
                    const formattedSql = formatSqlForDisplay(data.query);
                    let queryHtml = `<pre>${formattedSql}</pre>`;
                    
                    // Add note about query adjustment if present
                    if (data.query_note) {
                        queryHtml += `<div class="alert alert-info mt-2 small">${data.query_note}</div>`;
                    }
                    
                    document.getElementById('sqlQuery').innerHTML = queryHtml;
                } else {
                    document.getElementById('sqlQuery').innerHTML = '<p class="text-muted">No SQL query could be extracted from the response</p>';
                }
                
                // Display text results in the Results Description section
                if (data.success) {
                    // Display text results in the top right panel
                    document.getElementById('results').innerHTML = `<p>${data.result || "No text results available"}</p>`;
                    
                    // Check if we have tabular data to display
                    if (data.table_data && data.table_data.is_tabular) {
                        // If we have successful table data, hide any error message
                        document.getElementById('sqlError').style.display = 'none';
                    }
                    // Otherwise, if we have a SQL error, show it
                    else if (data.sql_error) {
                        const errorElement = document.getElementById('sqlError');
                        errorElement.innerHTML = `<strong>SQL Execution Error:</strong> ${data.sql_error}`;
                        errorElement.style.display = 'block';
                    }
                    
                    // Now process the table data if available
                    if (data.table_data && data.table_data.is_tabular) {
                        // Create a table for the data
                        let tableHTML = '<table class="results-table"><thead><tr>';
                        
                        // Add table headers
                        data.table_data.columns.forEach(column => {
                            tableHTML += `<th>${column}</th>`;
                        });
                        
                        tableHTML += '</tr></thead><tbody>';
                        
                        // Add table rows
                        data.table_data.rows.forEach(row => {
                            tableHTML += '<tr>';
                            row.forEach(cell => {
                                // Handle null values and format the cell
                                const cellValue = cell === null ? 'NULL' : cell;
                                tableHTML += `<td>${cellValue}</td>`;
                            });
                            tableHTML += '</tr>';
                        });
                        
                        tableHTML += '</tbody></table>';
                        
                        document.getElementById('tableResults').innerHTML = tableHTML;
                    } else if (!data.sql_error) {
                        // No table and no error means we should indicate no tabular data
                        document.getElementById('tableResults').innerHTML = '<p class="text-muted text-center my-4">No tabular data available</p>';
                    }
                    
                    // Add debug info
                    const debugSection = document.createElement('details');
                    debugSection.className = 'debug-info';
                    debugSection.innerHTML = `
                        <summary>Debug Info</summary>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    `;
                    document.getElementById('debugContainer').appendChild(debugSection);
                } else {
                    document.getElementById('results').innerHTML = `<div class="alert alert-danger">Error: ${data.error}</div>`;
                    document.getElementById('tableResults').innerHTML = '';
                }
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('sqlQuery').innerHTML = '';
                document.getElementById('results').innerHTML = `<div class="alert alert-danger">Error connecting to server: ${error.message}</div>`;
            }
        });
        
        // Allow pressing Enter to submit
        document.getElementById('queryInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('submitBtn').click();
            }
        });
    </script>
</body>
</html>
    """)

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)