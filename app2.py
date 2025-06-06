import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
import numpy as np
import os
import json
import requests
from datetime import datetime, date
import dotenv
from sqlalchemy import create_engine
import urllib.parse

# Load environment variables from .env file
dotenv.load_dotenv()    

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# PostgreSQL connection parameters
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "employee_reports")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

st.set_page_config(layout="wide")
st.title("📊 Employee Reports Dashboard")

if 'current_df' not in st.session_state:
    st.session_state.current_df = pd.DataFrame()

# Create PostgreSQL connection string
def get_connection_string():
    password = urllib.parse.quote_plus(POSTGRES_PASSWORD)
    return f"postgresql://{POSTGRES_USER}:{password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Create database connection - Fixed to not close connection
@st.cache_resource
def get_db_connection():
    try:
        # Test connection
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        return conn
    except Exception as e:
        st.error(f"Failed to connect to PostgreSQL database: {e}")
        st.error("Please check your database connection parameters in the .env file:")
        st.code("""
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=employee_reports
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
        """)
        st.stop()

# Get SQLAlchemy engine for pandas
@st.cache_resource
def get_engine():
    try:
        engine = create_engine(get_connection_string())
        return engine
    except Exception as e:
        st.error(f"Failed to create database engine: {e}")
        st.stop()

# Initialize connections
conn = get_db_connection()
engine = get_engine()

# Check required tables - Fixed to handle connection properly
@st.cache_data
def check_database_schema():
    """Check if all required tables exist"""
    required_tables = [
        'employee_master', 
        'employee_exit_report', 
        'employee_work_profile', 
        'employee_experience_report',
        'daily_attendance', 
        'timesheets'
    ]
    
    try:
        # Use engine instead of direct connection for better handling
        existing_tables_df = pd.read_sql("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """, engine)
        
        existing_table_names = existing_tables_df['table_name'].tolist()
        missing_tables = [table for table in required_tables if table not in existing_table_names]
        
        return existing_table_names, missing_tables, required_tables
        
    except Exception as e:
        st.error(f"Error checking database schema: {e}")
        return [], [], []

# Check database schema
existing_tables, missing_tables, required_tables = check_database_schema()

if missing_tables:
    st.error(f"Missing required tables: {', '.join(missing_tables)}")
    st.info(f"Existing tables: {', '.join(existing_tables)}")
    st.stop()

tab1, tab2, tab3 = st.tabs(["📋 Predefined Reports", "🔍 Custom Queries", "🤖 AI Query Assistant"])

with tab1:
    report_options = [
        "Employee Roster",
        "Exit Report", 
        "Work Profile",
        "Experience Summary",
        "Daily Attendance with Timesheet Verification",
        "Project Master Report",
        "Employee Project Summary"
    ]

    choice = st.selectbox("Select a report", report_options)

    try:
        if choice == "Employee Roster":
            df = pd.read_sql("SELECT * FROM employee_master", engine)
            if df.empty:
                st.warning("No employee data found.")
            else:
                st.dataframe(df)
                st.session_state.current_df = df

        elif choice == "Exit Report":
            df = pd.read_sql("SELECT * FROM employee_exit_report", engine)
            if df.empty:
                st.warning("No exit report data found.")
            else:
                st.dataframe(df)
                st.session_state.current_df = df

        elif choice == "Work Profile":
            df = pd.read_sql("SELECT * FROM employee_work_profile", engine)
            if df.empty:
                st.warning("No work profile data found.")
            else:
                st.dataframe(df) 
                st.session_state.current_df = df

        elif choice == "Experience Summary":
            df = pd.read_sql("SELECT * FROM employee_experience_report", engine)
            if df.empty:
                st.warning("No experience data found.")
            else:
                st.dataframe(df)
                st.session_state.current_df = df

        elif choice == "Daily Attendance with Timesheet Verification":
            query = """
                SELECT
                    a.employee_code,
                    a.date,
                    a.clock_in_time,
                    a.clock_out_time,
                    a.total_hours as attendance_hours,
                    COALESCE(t.project_name, 'No Project') as project_name,
                    COALESCE(t.hours_worked, 0) as hours_worked
                FROM daily_attendance a
                LEFT JOIN timesheets t
                ON a.employee_code = t.employee_code AND a.date = t.date
                ORDER BY a.date, a.employee_code
            """
            df = pd.read_sql(query, engine)
            if df.empty:
                st.warning("No attendance data found.")
            else:
                st.dataframe(df)
                st.session_state.current_df = df
            
        elif choice == "Project Master Report":
            # Check if timesheets table has data
            timesheet_count_df = pd.read_sql("SELECT COUNT(*) as count FROM timesheets", engine)
            timesheet_count = timesheet_count_df.iloc[0]['count']
            
            if timesheet_count == 0:
                st.warning("No timesheet data found.")
            else:
                # Comprehensive report about all projects
                query = """
                    SELECT 
                        DISTINCT t.project_id,
                        t.project_name,
                        COUNT(DISTINCT t.employee_code) as total_employees,
                        ROUND(SUM(t.hours_worked)::numeric, 2) as total_hours,
                        MIN(t.date) as start_date,
                        MAX(t.date) as latest_activity_date,
                        COUNT(DISTINCT t.date) as active_days
                    FROM timesheets t
                    GROUP BY t.project_id, t.project_name
                    ORDER BY t.project_id
                """
                
                project_summary_df = pd.read_sql(query, engine)
                
                if project_summary_df.empty:
                    st.warning("No project data found.")
                else:
                    # Get project details for each project
                    for i, row in project_summary_df.iterrows():
                        project_id = row["project_id"]
                        st.subheader(f"Project: {row['project_name']} ({project_id})")
                        
                        # Display project summary
                        summary_metrics = {
                            "Total Employees": int(row["total_employees"]),
                            "Total Hours": f"{row['total_hours']:.1f}",
                            "Start Date": str(row["start_date"]),
                            "Latest Activity": str(row["latest_activity_date"]),
                            "Active Days": int(row["active_days"])
                        }
                        
                        # Show summary metrics in columns
                        cols = st.columns(len(summary_metrics))
                        for col, (metric_name, metric_value) in zip(cols, summary_metrics.items()):
                            col.metric(metric_name, metric_value)
                        
                        # Get employee details for this project
                        emp_query = """
                            SELECT 
                                e.employee_name,
                                e.department,
                                ROUND(SUM(t.hours_worked)::numeric, 2) as total_hours,
                                COUNT(DISTINCT t.date) as days_worked,
                                MIN(t.date) as first_day,
                                MAX(t.date) as last_day
                            FROM timesheets t
                            JOIN employee_master e ON t.employee_code = e.employee_code
                            WHERE t.project_id = %(project_id)s
                            GROUP BY e.employee_name, e.department
                            ORDER BY total_hours DESC
                        """
                        project_employees_df = pd.read_sql(emp_query, engine, params={"project_id": project_id})
                        
                        # Display employees on this project
                        if not project_employees_df.empty:
                            st.dataframe(project_employees_df)
                        else:
                            st.info("No employee data found for this project.")
                        
                        # Add a separator between projects
                        st.markdown("---")
                
                # Store for analysis tools
                st.session_state.current_df = project_summary_df
            
        elif choice == "Employee Project Summary":
            # Check if we have employee data
            emp_count_df = pd.read_sql("SELECT COUNT(*) as count FROM employee_master", engine)
            emp_count = emp_count_df.iloc[0]['count']
            
            if emp_count == 0:
                st.warning("No employee data found.")
            else:
                # Comprehensive report about employees and their projects
                query = """
                    SELECT
                        e.*,
                        COALESCE((SELECT COUNT(DISTINCT t.project_id) 
                                 FROM timesheets t 
                                 WHERE t.employee_code = e.employee_code), 0) as projects_count,
                        COALESCE((SELECT ROUND(SUM(t.hours_worked)::numeric, 2) 
                                 FROM timesheets t 
                                 WHERE t.employee_code = e.employee_code), 0) as total_hours_worked
                    FROM employee_master e
                    ORDER BY e.employee_code
                """
                
                emp_master_df = pd.read_sql(query, engine)
                
                if emp_master_df.empty:
                    st.warning("No employee data found.")
                else:
                    # Create expandable sections for each employee
                    for i, row in emp_master_df.iterrows():
                        emp_code = row["employee_code"]
                        emp_name = row["employee_name"]
                        
                        with st.expander(f"{emp_name} ({emp_code}) - {row['department']} - {row['projects_count']} Projects"):
                            # Show employee details
                            st.write(f"**Email:** {row.get('email', 'N/A')}")
                            st.write(f"**Mobile Number:** {row.get('mobile_number', 'N/A')}")
                            st.write(f"**Total Hours:** {row['total_hours_worked']:.1f}")
                            
                            # Get project details for this employee
                            proj_query = """
                                SELECT 
                                    t.project_id,
                                    t.project_name,
                                    ROUND(SUM(t.hours_worked)::numeric, 2) as total_hours,
                                    COUNT(DISTINCT t.date) as days_worked,
                                    MIN(t.date) as first_day,
                                    MAX(t.date) as last_day
                                FROM timesheets t
                                WHERE t.employee_code = %(emp_code)s
                                GROUP BY t.project_id, t.project_name
                                ORDER BY total_hours DESC
                            """
                            emp_projects_df = pd.read_sql(proj_query, engine, params={"emp_code": emp_code})
                            
                            # Display projects for this employee
                            if not emp_projects_df.empty:
                                st.dataframe(emp_projects_df)
                            else:
                                st.info("No project assignments found for this employee.")
                
                # Store for analysis tools
                st.session_state.current_df = emp_master_df
            
    except Exception as e:
        st.error(f"Error executing query: {e}")
        st.error(f"Query details: {str(e)}")

with tab2:
    st.header("Custom Query Builder")
    
    # Cache the filter options to avoid repeated queries
    @st.cache_data
    def get_filter_options():
        try:
            # Get list of employee names with null handling
            employee_query = """
                SELECT DISTINCT employee_name 
                FROM employee_master 
                WHERE employee_name IS NOT NULL AND employee_name != ''
                ORDER BY employee_name
            """
            employee_names_df = pd.read_sql(employee_query, engine)
            employee_names = employee_names_df["employee_name"].tolist()
            
            # Get list of departments with null handling
            dept_query = """
                SELECT DISTINCT department 
                FROM employee_master 
                WHERE department IS NOT NULL AND department != ''
                ORDER BY department
            """
            departments_df = pd.read_sql(dept_query, engine)
            departments = departments_df["department"].tolist()
            
            # Get list of projects with null handling
            proj_query = """
                SELECT DISTINCT project_name 
                FROM timesheets 
                WHERE project_name IS NOT NULL AND project_name != ''
                ORDER BY project_name
            """
            projects_df = pd.read_sql(proj_query, engine)
            projects = projects_df["project_name"].tolist()
            
            return employee_names, departments, projects
            
        except Exception as e:
            st.error(f"Error loading filter options: {e}")
            return [], [], []
    
    employee_names, departments, projects = get_filter_options()
    
    # Create filter columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_employees = st.multiselect("Select Employees", options=["All"] + employee_names, default=["All"])
    
    with col2:
        selected_departments = st.multiselect("Select Departments", options=["All"] + departments, default=["All"])
    
    with col3:
        selected_projects = st.multiselect("Select Projects", options=["All"] + projects, default=["All"])
    
    # Create date range filter
    col4, col5 = st.columns(2)
    with col4:
        start_date = st.date_input("Start Date", value=None)
    with col5:
        end_date = st.date_input("End Date", value=None)
    
    # Report type selection for custom query
    report_type = st.selectbox(
        "Select Report Type", 
        ["Employee Details", "Project Assignments", "Attendance Records", "Timesheet Summary"]
    )
    
    # Build the query
    if st.button("Generate Report", key="custom_query_report"):
        try:
            df = pd.DataFrame()  # Initialize empty dataframe
            
            if report_type == "Employee Details":
                query = "SELECT * FROM employee_master WHERE 1=1"
                params = {}
                
                if "All" not in selected_employees and selected_employees:
                    placeholders = ",".join([f"%(emp_{i})s" for i in range(len(selected_employees))])
                    query += f" AND employee_name IN ({placeholders})"
                    for i, emp in enumerate(selected_employees):
                        params[f"emp_{i}"] = emp
                
                if "All" not in selected_departments and selected_departments:
                    placeholders = ",".join([f"%(dept_{i})s" for i in range(len(selected_departments))])
                    query += f" AND department IN ({placeholders})"
                    for i, dept in enumerate(selected_departments):
                        params[f"dept_{i}"] = dept
                
                df = pd.read_sql(query, engine, params=params)
                
            elif report_type == "Project Assignments":
                query = """
                    SELECT 
                        t.date,
                        t.employee_code,
                        e.employee_name,
                        e.department,
                        t.project_id,
                        t.project_name,
                        t.hours_worked
                    FROM timesheets t
                    JOIN employee_master e ON t.employee_code = e.employee_code
                    WHERE 1=1
                """
                params = []
                
                if "All" not in selected_employees and selected_employees:
                    placeholders = ",".join(["%s" for _ in selected_employees])
                    query += f" AND e.employee_name IN ({placeholders})"
                    params.extend(selected_employees)
                
                if "All" not in selected_departments and selected_departments:
                    placeholders = ",".join(["%s" for _ in selected_departments])
                    query += f" AND e.department IN ({placeholders})"
                    params.extend(selected_departments)
                
                if "All" not in selected_projects and selected_projects:
                    placeholders = ",".join(["%s" for _ in selected_projects])
                    query += f" AND t.project_name IN ({placeholders})"
                    params.extend(selected_projects)
                
                if start_date:
                    query += " AND t.date >= %s"
                    params.append(start_date.strftime('%Y-%m-%d'))
            
                if end_date:
                    query += " AND t.date <= %s"
                    params.append(end_date.strftime('%Y-%m-%d'))
                
                query += " ORDER BY t.date, e.employee_name"
                
                df = pd.read_sql(query, engine, params=params)
                
            elif report_type == "Attendance Records":
                query = """
                    SELECT 
                        a.date,
                        a.employee_code, 
                        e.employee_name,
                        e.department,
                        a.clock_in_time,
                        a.clock_out_time,
                        a.total_hours
                    FROM daily_attendance a
                    JOIN employee_master e ON a.employee_code = e.employee_code
                    WHERE 1=1
                """
                params = []
                
                if "All" not in selected_employees and selected_employees:
                    placeholders = ",".join(["%s" for _ in selected_employees])
                    query += f" AND e.employee_name IN ({placeholders})"
                    params.extend(selected_employees)
                
                if "All" not in selected_departments and selected_departments:
                    placeholders = ",".join(["%s" for _ in selected_departments])
                    query += f" AND e.department IN ({placeholders})"
                    params.extend(selected_departments)
                
                if start_date:
                    query += " AND a.date >= %s"
                    params.append(start_date.strftime('%Y-%m-%d'))
            
                if end_date:
                    query += " AND a.date <= %s"
                    params.append(end_date.strftime('%Y-%m-%d'))
                
                query += " ORDER BY a.date, e.employee_name"
                
                df = pd.read_sql(query, engine, params=params)
                
            elif report_type == "Timesheet Summary":
                query = """
                    SELECT 
                        e.employee_name,
                        e.department,
                        t.project_name, 
                        ROUND(SUM(t.hours_worked)::numeric, 2) as total_hours
                    FROM timesheets t
                    JOIN employee_master e ON t.employee_code = e.employee_code
                    WHERE 1=1
                """
                params = []
                
                if "All" not in selected_employees and selected_employees:
                    placeholders = ",".join(["%s" for _ in selected_employees])
                    query += f" AND e.employee_name IN ({placeholders})"
                    params.extend(selected_employees)
                
                if "All" not in selected_departments and selected_departments:
                    placeholders = ",".join(["%s" for _ in selected_departments])
                    query += f" AND e.department IN ({placeholders})"
                    params.extend(selected_departments)
                
                if "All" not in selected_projects and selected_projects:
                    placeholders = ",".join(["%s" for _ in selected_projects])
                    query += f" AND t.project_name IN ({placeholders})"
                    params.extend(selected_projects)
                
                if start_date:
                    query += " AND t.date >= %s"
                    params.append(start_date.strftime('%Y-%m-%d'))
            
                if end_date:
                    query += " AND t.date <= %s"
                    params.append(end_date.strftime('%Y-%m-%d'))
                
                query += " GROUP BY e.employee_name, e.department, t.project_name"
                query += " ORDER BY e.employee_name, t.project_name"
                
                df = pd.read_sql(query, engine, params=params)
            
            # Store the dataframe in session state and display it
            if not df.empty:
                st.session_state.current_df = df
                st.dataframe(df)
                st.success(f"Report generated successfully! Found {len(df)} records.")
            else:
                st.warning("No data found matching the selected criteria.")
            
        except Exception as e:
            st.error(f"Error generating report: {e}")
            df = pd.DataFrame()

with tab3:
    st.header("AI Query Assistant")
    st.info("Describe what you want to find out in plain English, and let AI generate the SQL query for you.")
    
    user_query = st.text_area("What would you like to know?", 
        placeholder="Example: Show me all employees in the Marketing department who worked on Project PRJ003 in June 2025")
    
    if st.button("Generate Report", key="ai_query_report"):
        if not user_query:
            st.warning("Please enter a query description.")
        else:
            with st.spinner("Generating SQL query..."):
                try:
                    # Get database schema information for context
                    @st.cache_data
                    def get_database_context():
                        table_schema = {}
                        sample_data = {}
                        
                        for table in required_tables:
                            try:
                                schema_query = f"""
                                    SELECT column_name, data_type 
                                    FROM information_schema.columns 
                                    WHERE table_name = '{table}' 
                                    ORDER BY ordinal_position
                                """
                                schema_df = pd.read_sql(schema_query, engine)
                                table_schema[table] = schema_df.to_dict(orient='records')
                                
                                # Sample data for each table (first 5 rows)
                                sample_query = f"SELECT * FROM {table} LIMIT 5"
                                sample_df = pd.read_sql(sample_query, engine)
                                sample_data[table] = sample_df.to_dict(orient='records')
                            except Exception as e:
                                st.warning(f"Could not get schema/data for table {table}: {e}")
                                table_schema[table] = []
                                sample_data[table] = []
                        
                        return table_schema, sample_data
                    
                    table_schema, sample_data = get_database_context()
                    
                    # Create context message
                    context = {
                        "database_tables": required_tables,
                        "table_schemas": table_schema,
                        "sample_data": sample_data,
                        "query_requirement": user_query
                    }
                    
                    # Custom JSON encoder to handle timestamps and dates
                    class CustomJSONEncoder(json.JSONEncoder):
                        def default(self, obj):
                            if isinstance(obj, (datetime, date)):
                                return obj.isoformat()
                            if pd.isna(obj):
                                return None
                            try:
                                return super().default(obj)
                            except TypeError:
                                return str(obj)
                    
                    # Prepare API request
                    api_key = GEMINI_API_KEY
                    if not api_key:
                        st.error("GEMINI_API_KEY not found in environment variables. Please set it in your .env file.")
                        st.stop()
                        
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
                    
                    prompt = f"""
                    You are a database expert who helps convert natural language queries to SQL queries for PostgreSQL.

                    Here are the tables in the database:
                    {json.dumps(context['table_schemas'], indent=2, cls=CustomJSONEncoder)}

                    Here's a sample of each table's data:
                    {json.dumps(context['sample_data'], indent=2, cls=CustomJSONEncoder)}

                    The user wants the following information:
                    {user_query}

                    IMPORTANT: 
                    - This is a PostgreSQL database, so use PostgreSQL syntax
                    - Use ROUND(column::numeric, 2) for rounding numeric values
                    - Use %s for parameterized queries instead of ?
                    - All column names are lowercase (e.g., employee_name, not "Employee Name")
                    - Check which columns exist in which tables before writing queries
                    - The employee_master table contains employee_name and basic employee information  
                    - The timesheets table contains project assignments and hours but NOT employee names
                    - Join tables appropriately to get the information needed

                    Please generate a valid PostgreSQL SQL query.
                    Make sure to use DISTINCT or appropriate GROUP BY clauses to avoid duplicate rows.
                    Return only the SQL query without any explanation or additional text.
                    Your SQL query should be wrapped in triple backticks like this:
                    ```
                    SELECT * FROM table;
                    ```
                    """
                    
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    
                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {
                                        "text": prompt
                                    }
                                ]
                            }
                        ]
                    }
                    
                    # Make API request
                    response = requests.post(url, headers=headers, json=payload)
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        response_text = response_data['candidates'][0]['content']['parts'][0]['text']
                        
                        # Extract SQL query from response
                        import re
                        sql_match = re.search(r"```(?:sql)?\n([\s\S]*?)\n```", response_text)
                        
                        if sql_match:
                            sql_query = sql_match.group(1).strip()
                            
                            # Display the generated SQL
                            st.subheader("Generated SQL Query:")
                            st.code(sql_query, language="sql")
                            
                            # Execute the query
                            with st.spinner("Executing query..."):
                                try:
                                    result_df = pd.read_sql(sql_query, engine)
                                    
                                    # Store results and display
                                    st.session_state.current_df = result_df
                                    st.subheader("Query Results:")
                                    st.dataframe(result_df)
                                    st.success(f"Query executed successfully! Found {len(result_df)} records.")
                                except Exception as e:
                                    st.error(f"Error executing query: {str(e)}")
                        else:
                            st.error("Could not extract SQL query from API response")
                            st.text("Full response:")
                            st.text(response_text)
                    else:
                        st.error(f"API request failed with status code {response.status_code}")
                        st.error(response.text)
                        
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# Note: Removed the connection closing code as it was causing the issue
# The @st.cache_resource decorator will handle connection lifecycle properly
