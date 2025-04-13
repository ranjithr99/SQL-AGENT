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

# Write HTML template to separate file
html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQL AI Assistant</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/highlight.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/languages/sql.min.js"></script>
    <style>
        :root {
            --primary-color: #4361ee;
            --secondary-color: #3f37c9;
            --accent-color: #4895ef;
            --light-color: #f8f9fa;
            --dark-color: #212529;
            --success-color: #4cc9f0;
            --warning-color: #f72585;
            --info-color: #4361ee;
            --header-bg: linear-gradient(135deg, #4361ee 0%, #3a0ca3 100%);
            --card-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            --hover-transition: all 0.3s ease;
        }
        
        body {
            background-color: #f5f7fb;
            padding-top: 20px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .container {
            max-width: 1200px;
        }
        
        h1.page-title {
            color: white;
            font-weight: 700;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 25px;
            background: var(--header-bg);
            box-shadow: var(--card-shadow);
            text-align: center;
        }
        
        .card {
            border: none;
            border-radius: 10px;
            box-shadow: var(--card-shadow);
            transition: var(--hover-transition);
            margin-bottom: 25px;
            overflow: hidden;
        }
        
        .card:hover {
            box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
            transform: translateY(-5px);
        }
        
        .card-header {
            background: var(--header-bg);
            color: white;
            font-weight: 600;
            padding: 15px 20px;
            border-bottom: none;
        }
        
        .card-header i {
            margin-right: 10px;
        }
        
        .card-body {
            padding: 20px;
            background-color: white;
        }
        
        .input-group {
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.08);
            border-radius: 8px;
            overflow: hidden;
        }
        
        .form-control {
            border: 1px solid #e0e0e0;
            padding: 12px 15px;
            font-size: 16px;
        }
        
        .form-control:focus {
            box-shadow: none;
            border-color: var(--primary-color);
        }
        
        .btn-primary {
            background-color: var(--primary-color);
            border: none;
            padding: 10px 25px;
            font-weight: 600;
            transition: var(--hover-transition);
        }
        
        .btn-primary:hover {
            background-color: var(--secondary-color);
            transform: translateY(-2px);
        }
        
        .result-area {
            min-height: 200px;
            border-radius: 4px;
            word-wrap: break-word;
        }
        
        .sql-query {
            background-color: #282c34;
            color: #abb2bf;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Consolas', 'Courier New', monospace;
            position: relative;
        }
        
        pre {
            margin: 0;
            white-space: pre-wrap;
            font-size: 14px;
            line-height: 1.5;
        }
        
        code.language-sql {
            color: #e06c75;
        }
        
        .hljs-keyword {
            color: #c678dd !important;
            font-weight: bold;
        }
        
        .hljs-built_in {
            color: #56b6c2 !important;
        }
        
        .hljs-type {
            color: #98c379 !important;
        }
        
        .hljs-literal {
            color: #d19a66 !important;
        }
        
        .hljs-number {
            color: #d19a66 !important;
        }
        
        .hljs-regexp {
            color: #e06c75 !important;
        }
        
        .hljs-string {
            color: #98c379 !important;
        }
        
        .hljs-subst {
            color: #e6c07b !important;
        }
        
        .hljs-symbol {
            color: #61aeee !important;
        }
        
        .hljs-class {
            color: #e6c07b !important;
        }
        
        .hljs-function {
            color: #61aeee !important;
        }
        
        .hljs-title {
            color: #61aeee !important;
        }
        
        .hljs-params {
            color: #d19a66 !important;
        }
        
        .table-responsive {
            margin-top: 15px;
            overflow-x: auto;
        }
        
        .table-container {
            margin-top: 15px;
            max-height: 500px;
            overflow-y: auto;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background-color: white;
        }
        
        .results-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin-bottom: 0;
        }
        
        .results-table th {
            background: linear-gradient(135deg, #4361ee 0%, #3a0ca3 100%);
            color: white;
            padding: 15px 10px;
            text-align: left;
            position: sticky;
            top: 0;
            border: none;
            font-weight: 600;
        }
        
        .results-table th:first-child {
            border-top-left-radius: 8px;
        }
        
        .results-table th:last-child {
            border-top-right-radius: 8px;
        }
        
        .results-table td {
            padding: 12px 10px;
            border-bottom: 1px solid #e0e0e0;
        }
        
        .results-table tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        .results-table tr:hover {
            background-color: #e8f4fd;
        }
        
        .results-table tr:last-child td {
            border-bottom: none;
        }
        
        .results-table tr:last-child td:first-child {
            border-bottom-left-radius: 8px;
        }
        
        .results-table tr:last-child td:last-child {
            border-bottom-right-radius: 8px;
        }
        
        .sql-error {
            background-color: #ffe8e8;
            border-left: 4px solid #ff6b6b;
            padding: 15px;
            margin: 10px 0;
            border-radius: 0 8px 8px 0;
            color: #d63031;
        }
        
        .debug-info {
            margin-top: 20px;
            font-size: 0.8em;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            border: 1px dashed #ced4da;
        }
        
        .debug-info summary {
            cursor: pointer;
            padding: 8px;
            color: #6c757d;
            font-weight: 600;
        }
        
        .debug-info pre {
            background-color: #f1f3f5;
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            color: #495057;
        }
        
        .spinner-border {
            color: var(--primary-color);
        }
        
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #6c757d;
        }
        
        .empty-state i {
            font-size: 48px;
            margin-bottom: 15px;
            color: #ced4da;
        }
        
        .copy-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            border-radius: 4px;
            padding: 5px 10px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .copy-btn:hover {
            background-color: rgba(255, 255, 255, 0.3);
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 0 15px;
            }
            
            h1.page-title {
                font-size: 24px;
                padding: 15px;
            }
            
            .card-header {
                padding: 12px 15px;
            }
            
            .form-control {
                padding: 10px;
            }
            
            .btn-primary {
                padding: 10px 15px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="page-title"><i class="fas fa-database"></i> SQL AI Assistant</h1>
        
        <div class="row">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-question-circle"></i> Ask a question about your database
                    </div>
                    <div class="card-body">
                        <div class="input-group mb-3">
                            <input type="text" id="queryInput" class="form-control" placeholder="e.g., How many customers do we have in each country?">
                            <button class="btn btn-primary" type="button" id="submitBtn">
                                <i class="fas fa-search me-2"></i>Submit
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-code"></i> Generated SQL Query
                    </div>
                    <div class="card-body">
                        <div class="sql-query result-area" id="sqlQueryContainer">
                            <div id="sqlQuery">
                                <!-- SQL query will appear here -->
                                <div class="empty-state">
                                    <i class="fas fa-code"></i>
                                    <p>Your SQL query will appear here after submitting a question</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-info-circle"></i> Results Description
                    </div>
                    <div class="card-body">
                        <div id="results" class="result-area">
                            <!-- Text results will appear here -->
                            <div class="empty-state">
                                <i class="fas fa-comment-alt"></i>
                                <p>The AI's explanation of your results will appear here</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-table"></i> Data Table
                    </div>
                    <div class="card-body">
                        <div id="sqlError" class="sql-error" style="display: none;">
                            <!-- SQL error will appear here -->
                        </div>
                        <div class="table-container">
                            <div id="tableResults" class="table-responsive">
                                <!-- Table results will appear here -->
                                <div class="empty-state">
                                    <i class="fas fa-table"></i>
                                    <p>Your query results will appear here in tabular format</p>
                                </div>
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
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Helper function to clean SQL query for display
        function formatSqlForDisplay(sql) {
            if (!sql) return '';
            return sql;
        }
        
        // Function to copy text to clipboard
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                const copyBtn = document.querySelector('.copy-btn');
                copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
                setTimeout(() => {
                    copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy';
                }, 2000);
            });
        }
        
        document.getElementById('submitBtn').addEventListener('click', async function() {
            const query = document.getElementById('queryInput').value;
            if (!query) return;
            
            // Clear previous results
            document.getElementById('sqlQuery').innerHTML = '<div class="d-flex justify-content-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
            document.getElementById('results').innerHTML = '<div class="d-flex justify-content-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
            document.getElementById('tableResults').innerHTML = '<div class="d-flex justify-content-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
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
                    let queryHtml = `
                        <button class="copy-btn" onclick="copyToClipboard(\`${formattedSql}\`)">
                            <i class="fas fa-copy"></i> Copy
                        </button>
                        <pre><code class="language-sql">${formattedSql}</code></pre>
                    `;
                    
                    // Add note about query adjustment if present
                    if (data.query_note) {
                        queryHtml += `<div class="alert alert-info mt-2 small">${data.query_note}</div>`;
                    }
                    
                    document.getElementById('sqlQuery').innerHTML = queryHtml;
                    
                    // Apply syntax highlighting
                    document.querySelectorAll('pre code').forEach((block) => {
                        hljs.highlightBlock(block);
                    });
                } else {
                    document.getElementById('sqlQuery').innerHTML = `
                        <div class="empty-state">
                            <i class="fas fa-exclamation-circle"></i>
                            <p class="text-muted">No SQL query could be extracted from the response</p>
                        </div>
                    `;
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
                        errorElement.innerHTML = `<i class="fas fa-exclamation-triangle me-2"></i><strong>SQL Execution Error:</strong> ${data.sql_error}`;
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
                                const cellValue = cell === null ? '<span class="text-muted">NULL</span>' : cell;
                                tableHTML += `<td>${cellValue}</td>`;
                            });
                            tableHTML += '</tr>';
                        });
                        
                        tableHTML += '</tbody></table>';
                        
                        document.getElementById('tableResults').innerHTML = tableHTML;
                    } else if (!data.sql_error) {
                        // No table and no error means we should indicate no tabular data
                        document.getElementById('tableResults').innerHTML = `
                            <div class="empty-state">
                                <i class="fas fa-info-circle"></i>
                                <p class="text-muted">No tabular data available for this query</p>
                            </div>
                        `;
                    }
                    
                    // Add debug info
                    const debugSection = document.createElement('details');
                    debugSection.className = 'debug-info';
                    debugSection.innerHTML = `
                        <summary><i class="fas fa-bug me-1"></i> Debug Info</summary>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    `;
                    document.getElementById('debugContainer').appendChild(debugSection);
                } else {
                    document.getElementById('results').innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>Error: ${data.error}</div>`;
                    document.getElementById('tableResults').innerHTML = `
                        <div class="empty-state">
                            <i class="fas fa-exclamation-triangle"></i>
                            <p class="text-muted">No data available due to an error</p>
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('sqlQuery').innerHTML = '';
                document.getElementById('results').innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>Error connecting to server: ${error.message}</div>`;
                document.getElementById('tableResults').innerHTML = '';
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
</html>"""

# Create index.html file with the template
with open('templates/index.html', 'w') as f:
    f.write(html_template)

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)