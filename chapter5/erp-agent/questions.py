"""
10 natural language questions, along with the "output column" hints for the Agent.

The hint only supplements schema-level hints such as "business definition + which columns to return and in what order",
without revealing specific numeric answers. The column order matches the return of reference.py for easy row-by-row comparison.
"""

QUESTIONS = [
    {
        "id": 1,
        "nl": "What is the average tenure of each employee?",
        "hint": "Tenure is calculated in days: for departed employees use leave_date, for active employees use today's date('now'),"
                "Calculate the average for all employees. Return only one column: average tenure in days.",
    },
    {
        "id": 2,
        "nl": "How many active employees are in each department?",
        "hint": "Active means leave_date is NULL. Return two columns: department, active employee count.",
    },
    {
        "id": 3,
        "nl": "Which department has the highest average employee level?",
        "hint": "Calculate the average level for all employees (including departed) grouped by department, and take the department with the highest average."
                "Return only one column: department name.",
    },
    {
        "id": 4,
        "nl": "How many new employees joined each department this year and last year?",
        "hint": "Count by year of hire_date. Return three columns: department, hires this year, hires last year;"
                "Only keep departments that had at least one hire this year or last year.",
    },
    {
        "id": 5,
        "nl": "What was the average salary of department A from March of the year before last to May of last year?",
        "hint": "Department A = R&D department; the time range refers to salary months from \"March of the year before last\" to \"May of last year\" (inclusive)."
                "Do not hardcode years; the time range can be written as:"
                "strftime('%Y-%m',pay_date) BETWEEN "
                "strftime('%Y-%m','now','-2 years','start of year','+2 months') AND "
                "strftime('%Y-%m','now','-1 year','start of year','+4 months')。"
                "Return only one column: average salary.",
    },
    {
        "id": 6,
        "nl": "Which department had a higher average salary last year, department A or department B?",
        "hint": "Department A = R&D department, department B = Sales department; only count salary records from last year."
                "（strftime('%Y',pay_date)=strftime('%Y','now','-1 year')）。"
                "Include all employees (including departed) in the department, do not filter by leave_date."
                "Return two columns: department, average salary (two rows, one for R&D and one for Sales).",
    },
    {
        "id": 7,
        "nl": "What is the average salary of employees at each level this year?",
        "hint": "Only count salary records from this year, group by level. Return two columns: level, average salary.",
    },
    {
        "id": 8,
        "nl": "What is the average salary in the most recent month for employees with tenure of less than one year, one to two years, and two to three years?",
        "hint": "Tenure is calculated by days from date('now')-hire_date: <365 days as \"less than one year\","
                "365~730 days as \"one to two years\", 730~1095 days as \"two to three years\", more than three years are not counted."
                "\"Most recent month salary\" refers to the salary record with the largest pay date for that employee. Calculate the average by tenure bracket."
                "Return two columns: bracket (values must be exactly \"less than one year\"/\"one to two years\"/\"two to three years\"), average salary.",
    },
    {
        "id": 9,
        "nl": "Who are the top 10 employees with the largest salary increase from last year to this year?",
        "hint": "For each employee, salary increase = average salary this year - average salary last year, only count employees who had salary in both last year and this year,"
                "Sort by salary increase descending and take the top 10. Return two columns: name, salary increase.",
    },
    {
        "id": 10,
        "nl": "Are there any cases of unpaid wages (an employee was still employed in a certain month but did not receive salary)?",
        "hint": "For each employee, their employed months range from the hire month to (for terminated employees, the termination month; for active employees, the current month)."
                "Check month by month whether there is a corresponding salary record, and find the missing (employee, month) pairs."
                "Return two columns: emp_id, month (format YYYY-MM)."
                "Recommended approach (include the 'end month' in the recursive CTE to avoid correlated subqueries):\n"
                "WITH RECURSIVE em(emp_id, m, end_m) AS (\n"
                "  SELECT emp_id, strftime('%Y-%m', hire_date),\n"
                "         COALESCE(strftime('%Y-%m', leave_date), strftime('%Y-%m','now'))\n"
                "  FROM employees\n"
                "  UNION ALL\n"
                "  SELECT emp_id, strftime('%Y-%m', date(m || '-01', '+1 month')), end_m\n"
                "  FROM em WHERE m < end_m)\n"
                "SELECT em.emp_id, em.m FROM em\n"
                "LEFT JOIN salaries s ON s.emp_id = em.emp_id "
                "AND strftime('%Y-%m', s.pay_date) = em.m\n"
                "WHERE s.emp_id IS NULL;",
    },
]

#  Questions that need to be presented 'in order' (for validation, comparing content by set is sufficient; this is only for display).
ORDERED = {9}
