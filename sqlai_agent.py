import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine, text
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.agents.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain.agents import AgentExecutor
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables
load_dotenv()

class SQLAIAgent:
    """
    An AI agent that translates natural language to SQL queries,
    executes them, and returns formatted results.
    """
    
    def __init__(
        self, 
        db_connection_string: str,
        google_api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash",
        temperature: float = 0.0,
        verbose: bool = False
    ):
        """
        Initialize the SQL AI Agent.
        
        Args:
            db_connection_string: SQLAlchemy connection string to the database
            google_api_key: Google AI API key (if not provided in env vars)
            model_name: LLM model to use (Gemini 2.0 Flash by default)
            temperature: Creativity of the model (0.0 = deterministic)
            verbose: Whether to print debug information
        """
        # Set API key
        if google_api_key:
            os.environ["GOOGLE_API_KEY"] = google_api_key
        
        # Initialize database connection
        self.db = SQLDatabase.from_uri(db_connection_string)
        self.engine = create_engine(db_connection_string)
        
        # Initialize LLM with Google Gemini
        self.llm = ChatGoogleGenerativeAI(
            temperature=temperature,
            model=model_name,
            verbose=verbose
        )
        
        # Create SQL toolkit and agent
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        self.agent_executor = create_sql_agent(
            llm=self.llm,
            toolkit=self.toolkit,
            verbose=verbose,
            top_k=100  # Return more examples for better context
        )
        
        # Schema caching
        self._schema_cache = None
        
        # Verbose flag
        self.verbose = verbose
    
    def get_schema(self) -> str:
        """
        Get the database schema as a string.
        """
        if self._schema_cache is None:
            self._schema_cache = self.db.get_table_info()
        return self._schema_cache
    
    def run_query(self, query: str) -> pd.DataFrame:
        """
        Execute a raw SQL query and return results as DataFrame.
        
        Args:
            query: SQL query to execute
            
        Returns:
            DataFrame with query results
        """
        if self.verbose:
            print(f"Executing SQL query: {query}")
            
        try:
            with self.engine.connect() as conn:
                return pd.read_sql_query(text(query), conn)
        except Exception as e:
            if self.verbose:
                print(f"Error executing query: {str(e)}")
            raise
    
    def process_natural_language(self, user_input: str) -> Dict[str, Any]:
        """
        Process natural language input and return query results.
        
        Args:
            user_input: Natural language query about the database
            
        Returns:
            Dictionary with query, results, and explanation
        """
        try:
            # Run the agent to get response
            response = self.agent_executor.run(user_input)
            
            if self.verbose:
                print("RAW RESPONSE:")
                print(response)
            
            # Extract SQL query from the response if available
            sql_query = self._extract_sql_from_response(response)
            
            # If no SQL query was found but we have a response, try a direct prompt
            if not sql_query and response:
                # Create a prompt template for extracting SQL
                template = """
                Based on the database schema below and the natural language query, 
                generate an SQL query that would answer the question.
                
                Schema:
                {schema}
                
                Question: {question}
                
                Previous analysis: {response}
                
                SQL Query (include only the SQL, no explanations):
                """
                
                prompt = PromptTemplate(
                    input_variables=["schema", "question", "response"],
                    template=template,
                )
                
                chain = LLMChain(llm=self.llm, prompt=prompt)
                sql_attempt = chain.run(
                    schema=self.get_schema(),
                    question=user_input,
                    response=response
                )
                
                # If this looks like SQL, use it
                if "SELECT" in sql_attempt.upper():
                    sql_query = sql_attempt.strip()
            
            result = {
                "success": True,
                "query": sql_query,
                "result": response,
                "explanation": f"Processed query: {user_input}",
                "raw_response": response
            }
            
            # If we have a SQL query, try to execute it and add the DataFrame to the result
            if sql_query:
                try:
                    df_result = self.run_query(sql_query)
                    # We don't directly add the DataFrame to avoid JSON serialization issues
                    # but we'll add it to a separate field
                    result["sql_result"] = df_result
                except Exception as e:
                    if self.verbose:
                        print(f"Error executing extracted SQL: {str(e)}")
                    result["sql_error"] = str(e)
            
            return result
            
        except Exception as e:
            if self.verbose:
                print(f"Error in process_natural_language: {str(e)}")
                
            return {
                "success": False,
                "error": str(e),
                "explanation": f"Error processing: {user_input}"
            }
    
    def _extract_sql_from_response(self, response: str) -> Optional[str]:
        """
        Extract SQL query from agent response if present.
        """
        # Check for SQL code blocks
        if "```sql" in response:
            # Extract between SQL code blocks
            sql_parts = response.split("```sql")
            if len(sql_parts) > 1:
                query_block = sql_parts[1].split("```")[0].strip()
                return query_block
        # Try looking for SQL without markdown formatting
        elif "SELECT" in response.upper():
            # Find lines containing SELECT statements
            lines = response.split('\n')
            for i, line in enumerate(lines):
                if "SELECT" in line.upper():
                    # Try to capture a complete SQL statement
                    statement = []
                    j = i
                    while j < len(lines) and ";" not in lines[j]:
                        statement.append(lines[j])
                        j += 1
                    if j < len(lines):
                        statement.append(lines[j])
                    return "\n".join(statement)
        return None
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze a potential SQL query for safety and optimization - concise version.
        
        Args:
            query: The SQL query to analyze
            
        Returns:
            Dictionary with analysis results
        """
        # Create a prompt for concise query analysis
        template = """
        Analyze this SQL query concisely (max 3-4 bullet points):
        
        {query}
        
        Provide only:
        • Safety (any risks?)
        • Performance (any optimizations?)
        • Correctness (any logical issues?)
        
        Keep each point to 1-2 sentences maximum.
        """
        
        prompt = PromptTemplate(
            input_variables=["query"],
            template=template,
        )
        
        chain = LLMChain(llm=self.llm, prompt=prompt)
        result = chain.run(query=query)
        
        return {
            "query": query,
            "analysis": result
        }

# Example usage
if __name__ == "__main__":
    import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    # Example connection to a SQLite database
    db_connection = "sqlite:///example.db"
    
    # Initialize the agent
    agent = SQLAIAgent(
        db_connection_string=db_connection,
        verbose=True
    )
    
    # Example query
    result = agent.process_natural_language(
        "How many customers do we have in each country?"
    )
    
    print("\nResult:", result)