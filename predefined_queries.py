from flask import Blueprint, jsonify, session, url_for, request, current_app
from functools import wraps
from config import ProductionConfig

predefined_queries_bp = Blueprint('predefined_queries', __name__)

# Dictionary mapping dropdown options to their respective SQL queries
PREDEFINED_QUERIES = {
    'style_info': """
        SELECT po_date, po_num, style_num_full, updated_date, total_qty_received,
    (qord1 + qord2 + qord3 + qord4 + qord5 + qord6 + qord7 + qord8 + qord9 + qord10 + qord11 + qord12) AS TTL_Order
    FROM plm_tp_bulk_items
    WHERE updated_date >= CURRENT_DATE - INTERVAL '1 day' AND total_qty_received <> 0
    ORDER BY updated_date DESC
    """,
    
    'inventory': """
        SELECT 
            i.product_id,
            s.style_name,
            i.size,
            i.color,
            i.quantity_available,
            i.last_stock_update
        FROM {schema}.inventory i
        JOIN {schema}.styles s ON i.style_id = s.style_id
        WHERE i.quantity_available > 0
        ORDER BY i.last_stock_update DESC
        LIMIT 1000
    """,
    
    'recent_orders': """
        SELECT 
            o.order_id,
            o.customer_id,
            s.style_name,
            o.quantity,
            o.order_date,
            o.status
        FROM {schema}.orders o
        JOIN {schema}.styles s ON o.style_id = s.style_id
        ORDER BY o.order_date DESC
        LIMIT 1000
    """
}

@predefined_queries_bp.route('/predefined-query/<query_type>', methods=['GET'])
def execute_predefined_query(query_type):
    """Execute a predefined query"""
    try:
        if query_type not in PREDEFINED_QUERIES:
            return jsonify({
                'success': False,
                'error': 'Invalid query type'
            }), 400

        schema = ProductionConfig.get_default_schema()
        query = PREDEFINED_QUERIES[query_type].format(schema=schema).strip()

        # Import execute_query function to handle the actual query execution
        from app import execute_query_internal
        test = execute_query_internal(query, schema)
        print(test)
        # Execute the query 
        return #execute_query_internal(query, schema)
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str('tanishq')
        }), 500
