-- Experiment 5-10 ERP Agent — PostgreSQL schema required by the book (two tables).
--
-- The runnable demo in this repository uses SQLite (zero dependencies, reproducible offline, see seed.py / demo.py);
-- This DDL provides the PostgreSQL version from the original book, convenient for migration to a real Postgres environment.
-- The table structures of the two dialects are consistent, with differences mainly in date functions:
--   SQLite:      strftime('%Y','now')        julianday(a)-julianday(b)   date('now','-1 year')
--   PostgreSQL:  EXTRACT(YEAR FROM now())     (a::date - b::date)         now() - interval '1 year'
--
-- Usage (requires PostgreSQL locally):
--   createdb erp
--   psql erp -f schema_postgres.sql

DROP TABLE IF EXISTS salaries;
DROP TABLE IF EXISTS employees;

-- Employee table: ID, name, department, level (higher number = higher level), hire date, termination date (NULL = active)
CREATE TABLE employees (
    emp_id      INTEGER     PRIMARY KEY,
    name        TEXT        NOT NULL,
    department  TEXT        NOT NULL,
    level       INTEGER     NOT NULL,
    hire_date   DATE        NOT NULL,
    leave_date  DATE                     -- NULL means active
);

-- Salary table: employee ID, pay date (one row per month, using the 1st of that month), monthly salary
CREATE TABLE salaries (
    emp_id      INTEGER     NOT NULL REFERENCES employees(emp_id),
    pay_date    DATE        NOT NULL,     -- One row per month, e.g., 2025-03-01
    salary      INTEGER     NOT NULL,
    PRIMARY KEY (emp_id, pay_date)
);

CREATE INDEX idx_salaries_pay_date ON salaries (pay_date);
