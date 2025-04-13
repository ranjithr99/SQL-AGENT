import os
import argparse
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv
from sqlai_agent import SQLAIAgent

load_dotenv()

def display_results(results, format="table"):
    """Display results in different formats."""
    if isinstance(results, pd.DataFrame):
        if format == "json":
            print(results.to_json(orient="records", indent=2))
        else:  # Default to table
            print(results.to_string(index=False))
    else:
        print(results)

def setup_sample_database(db_path):
    """Create a sample database for testing."""
    engine = create_engine(f"sqlite:///{db_path}")
    
    # Create sample tables
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            country TEXT,
            signup_date DATE
        )
        """))
        
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_date DATE,
            total_amount REAL,
            status TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        )
        """))
        
        # Insert sample data
        conn.execute(text("""
        INSERT OR IGNORE INTO customers VALUES
            (1, 'John Smith', 'john@example.com', 'USA', '2023-01-15'),
            (2, 'Maria Garcia', 'maria@example.com', 'Spain', '2023-02-20'),
            (3, 'Li Wei', 'li@example.com', 'China', '2023-03-10'),
            (4, 'Aisha Khan', 'aisha@example.com', 'India', '2023-01-25'),
            (5, 'Carlos Rodriguez', 'carlos@example.com', 'Mexico', '2023-04-05')
        """))
        
        conn.execute(text("""
        INSERT OR IGNORE INTO orders VALUES
            (101, 1, '2023-02-01', 150.75, 'Delivered'),
            (102, 2, '2023-03-15', 89.99, 'Shipped'),
            (103, 3, '2023-03-20', 245.50, 'Processing'),
            (104, 1, '2023-04-10', 45.25, 'Delivered'),
            (105, 4, '2023-04-12', 199.99, 'Shipped'),
            (106, 5, '2023-04-15', 120.00, 'Processing'),
            (107, 2, '2023-04-20', 65.50, 'Processing')
        """))
        
        conn.commit()
    
    return engine

def main():
    parser = argparse.ArgumentParser(description="SQL AI Agent CLI")
    parser.add_argument("--db", type=str, default="example.db", help="Database path")
    parser.add_argument("--setup", action="store_true", help="Set up sample database")
    parser.add_argument("--format", choices=["table", "json"], default="table", help="Output format")
    parser.add_argument("--query", type=str, help="Natural language query")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--schema", action="store_true", help="Show database schema")
    parser.add_argument("--api-key", type=str, help="Google API key")
    
    args = parser.parse_args()
    
    # Set up sample database if requested
    if args.setup:
        print(f"Setting up sample database at {args.db}")
        engine = setup_sample_database(args.db)
        print("Sample database created successfully!")
        
        # Print the schema
        inspector = inspect(engine)
        for table_name in inspector.get_table_names():
            print(f"\nTable: {table_name}")
            print("-" * 50)
            for column in inspector.get_columns(table_name):
                print(f"{column['name']} ({column['type']})")
        return
    
    # Create connection string
    db_connection = f"sqlite:///{args.db}"
    
    # Initialize agent
    agent = SQLAIAgent(
        db_connection_string=db_connection,
        google_api_key=args.api_key
    )
    
    # Show schema if requested
    if args.schema:
        print("Database Schema:")
        print(agent.get_schema())
        return
    
    # Process single query
    if args.query:
        result = agent.process_natural_language(args.query)
        if result["success"]:
            print("\nResults:")
            display_results(result["result"], args.format)
            if result["query"]:
                print("\nGenerated SQL:")
                print(result["query"])
        else:
            print(f"Error: {result['error']}")
        return
    
    # Interactive mode
    if args.interactive:
        print("SQL AI Agent Interactive Mode")
        print("Type 'exit' or 'quit' to end the session")
        print("Type 'schema' to see the database schema")
        
        while True:
            try:
                user_input = input("\nEnter your question: ")
                
                if user_input.lower() in ["exit", "quit"]:
                    break
                    
                if user_input.lower() == "schema":
                    print(agent.get_schema())
                    continue
                
                result = agent.process_natural_language(user_input)
                
                if result["success"]:
                    print("\nResults:")
                    display_results(result["result"], args.format)
                    if result["query"]:
                        print("\nGenerated SQL:")
                        print(result["query"])
                else:
                    print(f"Error: {result['error']}")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {str(e)}")
    else:
        # Show help if no operation specified
        parser.print_help()

if __name__ == "__main__":
    main()