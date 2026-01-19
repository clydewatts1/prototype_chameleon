"""
Test suite for Phase 2 sqlglot AST-based SQL validation.

This test suite validates the new sqlglot-based SQL validation that provides
mathematical verification of read-only queries through AST parsing.
"""

import sys
import os
import pytest

# Add server to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from common.security import validate_read_only, validate_single_statement, SecurityError

try:
    import sqlglot
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False


@pytest.mark.skipif(not SQLGLOT_AVAILABLE, reason="sqlglot not available")
class TestSqlglotValidation:
    """Test suite for sqlglot AST-based validation (Phase 2)."""
    
    def test_simple_select(self):
        """Test that simple SELECT queries are allowed."""
        sql = "SELECT * FROM users"
        validate_read_only(sql)  # Should not raise
        validate_single_statement(sql)  # Should not raise
    
    def test_select_with_where(self):
        """Test SELECT with WHERE clause."""
        sql = "SELECT id, name FROM users WHERE age > 18"
        validate_read_only(sql)
        validate_single_statement(sql)
    
    def test_select_with_join(self):
        """Test SELECT with JOIN."""
        sql = "SELECT u.id, p.name FROM users u JOIN profiles p ON u.id = p.user_id"
        validate_read_only(sql)
        validate_single_statement(sql)
    
    def test_select_with_subquery(self):
        """Test SELECT with subquery - AST validation handles this correctly."""
        sql = "SELECT * FROM (SELECT id, name FROM users WHERE active = 1) AS active_users"
        validate_read_only(sql)
        validate_single_statement(sql)
    
    def test_union_query(self):
        """Test UNION query - should be allowed as it's read-only."""
        sql = "SELECT id FROM users UNION SELECT id FROM admins"
        validate_read_only(sql)
        validate_single_statement(sql)
    
    def test_cte_query(self):
        """Test CTE (WITH clause) - should be allowed."""
        sql = "WITH active_users AS (SELECT * FROM users WHERE active = 1) SELECT * FROM active_users"
        validate_read_only(sql)
        validate_single_statement(sql)
    
    def test_complex_nested_select(self):
        """Test complex nested SELECT with multiple levels."""
        sql = """
        WITH regional_sales AS (
            SELECT region, SUM(amount) as total_sales
            FROM orders
            GROUP BY region
        )
        SELECT r.region, r.total_sales
        FROM regional_sales r
        WHERE r.total_sales > (SELECT AVG(total_sales) FROM regional_sales)
        """
        validate_read_only(sql)
        validate_single_statement(sql)
    
    def test_insert_blocked(self):
        """Test that INSERT is blocked by AST analysis."""
        sql = "INSERT INTO users (name) VALUES ('hacker')"
        with pytest.raises(SecurityError, match="Only SELECT statements are allowed"):
            validate_read_only(sql)
    
    def test_update_blocked(self):
        """Test that UPDATE is blocked by AST analysis."""
        sql = "UPDATE users SET password = 'hacked' WHERE id = 1"
        with pytest.raises(SecurityError, match="Only SELECT statements are allowed"):
            validate_read_only(sql)
    
    def test_delete_blocked(self):
        """Test that DELETE is blocked by AST analysis."""
        sql = "DELETE FROM users WHERE id = 1"
        with pytest.raises(SecurityError, match="Only SELECT statements are allowed"):
            validate_read_only(sql)
    
    def test_drop_blocked(self):
        """Test that DROP is blocked by AST analysis."""
        sql = "DROP TABLE users"
        with pytest.raises(SecurityError, match="Only SELECT statements are allowed"):
            validate_read_only(sql)
    
    def test_create_blocked(self):
        """Test that CREATE is blocked by AST analysis."""
        sql = "CREATE TABLE hackers (id INT)"
        with pytest.raises(SecurityError, match="Only SELECT statements are allowed"):
            validate_read_only(sql)
    
    def test_alter_blocked(self):
        """Test that ALTER is blocked by AST analysis."""
        sql = "ALTER TABLE users ADD COLUMN backdoor TEXT"
        with pytest.raises(SecurityError, match="Only SELECT statements are allowed"):
            validate_read_only(sql)
    
    def test_truncate_blocked(self):
        """Test that TRUNCATE is blocked by AST analysis."""
        sql = "TRUNCATE TABLE users"
        with pytest.raises(SecurityError, match="Only SELECT statements are allowed"):
            validate_read_only(sql)
    
    def test_grant_blocked(self):
        """Test that GRANT is blocked by AST analysis."""
        sql = "GRANT ALL PRIVILEGES ON users TO hacker"
        with pytest.raises(SecurityError, match="Only SELECT statements are allowed"):
            validate_read_only(sql)
    
    def test_merge_blocked(self):
        """Test that MERGE is blocked by AST analysis."""
        sql = """
        MERGE INTO users USING new_users 
        ON users.id = new_users.id
        WHEN MATCHED THEN UPDATE SET name = new_users.name
        """
        # Should be blocked, but might fail to parse with incomplete MERGE syntax
        # Either way, it should raise a SecurityError
        with pytest.raises(SecurityError):
            validate_read_only(sql)
    
    def test_multiple_statements_blocked(self):
        """Test that multiple statements are blocked by AST analysis."""
        sql = "SELECT * FROM users; DROP TABLE users"
        with pytest.raises(SecurityError, match="Multiple SQL statements"):
            validate_single_statement(sql)
    
    def test_nested_write_in_subquery_blocked(self):
        """
        Test that write operations nested in subqueries are detected.
        This is where AST validation really shines compared to regex.
        """
        # Note: This is a contrived example - most databases wouldn't allow this syntax
        # but it demonstrates the power of AST-based validation
        sql = "SELECT * FROM users WHERE id IN (SELECT id FROM (UPDATE users SET flag=1))"
        
        # The AST walker should detect the UPDATE even though it's nested
        with pytest.raises(SecurityError):
            validate_read_only(sql)
    
    def test_comments_preserved(self):
        """Test that SQL comments don't interfere with validation."""
        sql = """
        -- This is a comment
        SELECT * FROM users
        /* Multi-line comment */
        WHERE active = 1
        """
        validate_read_only(sql)
        validate_single_statement(sql)
    
    def test_case_insensitive(self):
        """Test that validation is case-insensitive."""
        sql_lower = "select * from users"
        sql_upper = "SELECT * FROM USERS"
        sql_mixed = "SeLeCt * FrOm UsErS"
        
        for sql in [sql_lower, sql_upper, sql_mixed]:
            validate_read_only(sql)
            validate_single_statement(sql)
    
    def test_window_functions_allowed(self):
        """Test that window functions in SELECT are allowed."""
        sql = """
        SELECT 
            name,
            salary,
            ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) as rank
        FROM employees
        """
        validate_read_only(sql)
        validate_single_statement(sql)
    
    def test_aggregate_functions_allowed(self):
        """Test that aggregate functions are allowed."""
        sql = "SELECT COUNT(*), AVG(salary), MAX(age) FROM users GROUP BY department"
        validate_read_only(sql)
        validate_single_statement(sql)


@pytest.mark.skipif(SQLGLOT_AVAILABLE, reason="Testing fallback when sqlglot not available")
class TestFallbackValidation:
    """Test that validation still works when sqlglot is not available."""
    
    def test_fallback_to_sqlparse(self):
        """Test that validation falls back to sqlparse when sqlglot unavailable."""
        sql = "SELECT * FROM users"
        validate_read_only(sql)  # Should work with sqlparse or regex fallback
    
    def test_fallback_blocks_write_operations(self):
        """Test that fallback methods still block write operations."""
        sql = "UPDATE users SET name = 'test'"
        with pytest.raises(SecurityError):
            validate_read_only(sql)
