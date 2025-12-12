# Retail Sample Data Generator

This folder contains a Jupyter Notebook that generates sample retail data for testing and demonstration purposes.

## Contents

- **`generate_retail_data.ipynb`**: Jupyter Notebook that creates a sample retail database
- **`retail_tools.yaml`**: MCP tool definitions for querying the retail data
- **`retail.db`**: Generated SQLite database (created when you run the notebook, not in version control)

## Database Schema

The notebook creates a retail database with the following tables:

### 1. `location`
Store and depot locations across Ireland.
- `loc_id` (INTEGER, PK): Location identifier
- `loc_type` (TEXT): 'Store' or 'Depot'
- `loc_name` (TEXT): Location name
- `loc_country` (TEXT): Country (Ireland)
- `loc_town` (TEXT): Town name

**Data**: 1 depot + 10 stores in different Irish towns

### 2. `item`
Retail product catalog with pricing.
- `item_id` (INTEGER, PK): Item identifier
- `item_name` (TEXT): Product name
- `item_type` (TEXT): Product type
- `department` (TEXT): Department (Mens, Womens, Kids, etc.)
- `section` (TEXT): Section within department
- `retail_price` (REAL): Selling price
- `cost_price` (REAL): Cost price

**Data**: 20 realistic retail items with proper margins

### 3. `sales_header`
Sales transaction headers.
- `sale_id` (INTEGER, PK): Sale identifier
- `loc_id` (INTEGER, FK): Store location
- `sales_date` (TEXT): Sale date in ISO 8601 format (YYYY-MM-DD)
- `tender_total` (REAL): Total transaction amount

**Data**: Last 30 days, 20-50 sales per store per day

### 4. `sales_line`
Individual line items for each sale.
- `sale_id` (INTEGER, FK): Sale identifier
- `item_id` (INTEGER, FK): Item identifier
- `sales_amount` (REAL): Line total (units × retail_price)
- `sales_units` (INTEGER): Quantity sold

**Data**: 1-5 random items per sale

### 5. `daily_stock`
Daily stock snapshots for all locations and items.
- `stock_date` (TEXT): Stock date in ISO 8601 format (YYYY-MM-DD)
- `loc_id` (INTEGER, FK): Location identifier
- `item_id` (INTEGER, FK): Item identifier
- `stock_on_hand_units` (INTEGER): Current stock level
- `stock_on_order_units` (INTEGER): Stock on order

**Data**: 30 days of stock snapshots for all locations and items

## Important: Date Handling

**All dates are stored as ISO 8601 text strings (YYYY-MM-DD)** following SQLite best practices, as SQLite does not have a native DATE type. This ensures:
- Consistent date formatting
- Proper string-based date comparisons
- Easy date filtering in SQL queries

## Usage

### Running the Notebook

1. Install Jupyter if you haven't already:
   ```bash
   pip install jupyter
   ```

2. Navigate to this directory:
   ```bash
   cd samples/retail
   ```

3. Start Jupyter Notebook:
   ```bash
   jupyter notebook
   ```

4. Open `generate_retail_data.ipynb` and run all cells to generate the database.

### Using the MCP Tools

The `retail_tools.yaml` file defines four MCP tools for querying the data:

1. **`get_sales_by_store`**: Retrieve sales for a specific store, optionally filtered by date
2. **`get_sales_by_item`**: Get sales summary for a specific item with date range filtering
3. **`get_stock_status`**: Check stock levels for an item at a location
4. **`get_daily_sales_summary`**: Get daily sales summary across all stores

To load these tools into the MCP server:
```bash
python server/load_specs.py samples/retail/retail_tools.yaml
```

## Example Queries

After generating the database, you can query it directly:

```bash
# Get all locations
sqlite3 retail.db "SELECT * FROM location;"

# Get sales for a specific date
sqlite3 retail.db "SELECT * FROM sales_header WHERE sales_date = '2025-12-12';"

# Get top-selling items
sqlite3 retail.db "
SELECT i.item_name, SUM(sl.sales_units) as total_sold
FROM item i
JOIN sales_line sl ON i.item_id = sl.item_id
GROUP BY i.item_id, i.item_name
ORDER BY total_sold DESC
LIMIT 10;
"

# Get stock levels for a specific date
sqlite3 retail.db "
SELECT l.loc_name, i.item_name, ds.stock_on_hand_units
FROM daily_stock ds
JOIN location l ON ds.loc_id = l.loc_id
JOIN item i ON ds.item_id = i.item_id
WHERE ds.stock_date = '2025-12-12'
LIMIT 10;
"
```

## Database Statistics

After running the notebook, the database will contain approximately:
- 11 locations (1 depot + 10 stores)
- 20 items
- 10,000+ sales transactions (30 days × 10 stores × 20-50 sales/day)
- 30,000+ sales line items (avg 3 items per sale)
- 6,600 stock records (30 days × 11 locations × 20 items)

Total database size: ~1-2 MB
