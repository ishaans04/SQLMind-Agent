# Product Requirements Document (PRD)

# SQLMind Agent

### AI-Powered Database Analyst using MCP

Version 1.0

---

# 1. Executive Summary

SQLMind Agent is an AI-powered database analysis platform that enables users to interact with databases using natural language.

Users can connect their databases, ask questions in plain English, and receive:

* Generated SQL
* Query results
* AI explanations
* Database insights

The platform uses NVIDIA NIM for reasoning and SQL generation while utilizing SQLMind MCP as the secure database execution layer.

---

# 2. Vision

Create a "ChatGPT for Databases" experience.

Instead of writing SQL manually, users should be able to ask:

"What are my top selling products?"

and receive:

* SQL query
* Result table
* Human-readable explanation

without writing SQL themselves.

---

# 3. Product Goals

## Primary Goals

* Natural Language → SQL
* Database Connectivity
* Secure Query Execution
* AI Result Explanation
* MCP Integration

## Secondary Goals

* Query History
* Database Schema Understanding
* Session Persistence
* Visual Analytics

---

# 4. Users

### Primary Users

* Students
* Data Analysts
* Startup Teams
* Non-Technical Business Users

### User Problems

Current:

Need SQL knowledge.

Desired:

Ask questions in English.

---

# 5. High-Level Architecture

User
↓
SQLMind Agent Website
↓
NVIDIA NIM
↓
SQLMind MCP
↓
SQLite / PostgreSQL Database

---

# 6. Supported Databases

## Version 1

### SQLite

User uploads:

company.db

### PostgreSQL

User enters:

Host

Port

Database Name

Username

Password

---

# 7. Technology Stack

## Frontend

Streamlit

Reason:

Fast development
Easy deployment
Python-only stack

---

## AI Layer

NVIDIA NIM

Models:

* Llama 3.1 8B Instruct
* Llama 3.3 70B (optional)

---

## Backend

Python

---

## Database Connectivity

SQLite

psycopg2 (PostgreSQL)

---

## MCP Integration

SQLMind MCP Server

Already developed.

---

## Data Processing

Pandas

---

## Environment Variables

python-dotenv

---

# 8. Folder Structure

SQLMind-Agent/

├── app.py

├── auth.py

├── database_connector.py

├── nim_client.py

├── mcp_client.py

├── prompts.py

├── query_history.py

├── config.py

├── requirements.txt

├── README.md

├── .env.example

├── assets/

└── logs/

---

# 9. Core User Flow

User opens website

↓

Login

↓

Choose Database Type

(SQLite / PostgreSQL)

↓

Connect Database

↓

AI fetches schema

↓

User asks question

↓

NVIDIA NIM generates SQL

↓

SQL sent to MCP

↓

MCP executes safely

↓

Results returned

↓

NIM explains results

↓

User receives answer

---

# 10. Authentication

Version 1:

Simple login

Fields:

* Username
* Password

Session-based authentication

No OAuth in Version 1.

---

# 11. Database Connection Module

## SQLite

User uploads:

database.db

System:

* validates file
* reads schema
* establishes connection

---

## PostgreSQL

User enters:

Host

Port

Database

Username

Password

System:

* validates connection
* retrieves schema
* stores session connection

---

# 12. AI Agent Workflow

Step 1

Retrieve schema.

---

Step 2

Build prompt:

Database schema
+
User question

---

Step 3

NVIDIA NIM generates SQL.

---

Step 4

Validate SQL.

---

Step 5

Send SQL to MCP:

run_select_query()

---

Step 6

Receive results.

---

Step 7

Generate explanation.

---

Step 8

Display answer.

---

# 13. User Interface

## Sidebar

Logo

Database Connection

Query History

Settings

Logout

---

## Main Area

Chat Interface

Example:

Ask a question...

[________________]

[Submit]

---

## Results Area

Generated SQL

Result Table

AI Explanation

---

# 14. Features

## Feature 1

Natural Language Querying

Example:

Show students with attendance below 75%.

---

## Feature 2

Generated SQL Display

User sees:

SELECT ...

---

## Feature 3

Result Table

Pandas DataFrame

---

## Feature 4

AI Explanation

Example:

3 students have attendance below 75%.

---

## Feature 5

Query History

Store:

Question

SQL

Timestamp

---

## Feature 6

Database Schema Viewer

Display:

Tables

Columns

Data Types

---

# 15. Safety Requirements

Only SELECT queries.

Block:

DROP

DELETE

UPDATE

INSERT

ALTER

TRUNCATE

CREATE

Handled by MCP.

---

# 16. Error Handling

Database connection failure

↓

Show friendly error.

---

Invalid SQL

↓

Display message.

---

Empty results

↓

Explain no records found.

---

NIM API failure

↓

Retry and display status.

---

# 17. Logging

Store:

timestamp

user query

generated SQL

execution status

response time

---

# 18. Deployment

Version 1

Localhost

---

Version 2

Render

or

Streamlit Community Cloud

---

# 19. Success Criteria

User can:

✓ Login

✓ Connect database

✓ Ask questions in English

✓ Generate SQL automatically

✓ Execute SQL safely through MCP

✓ View results

✓ Receive AI explanations

---

# 20. Resume Description

SQLMind Agent | NVIDIA NIM, MCP, Streamlit, PostgreSQL, SQLite

Developed an AI-powered database analyst that converts natural language into SQL queries, securely executes them through a custom MCP server, supports SQLite and PostgreSQL databases, and explains query results using NVIDIA NIM.
