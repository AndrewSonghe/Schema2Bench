"""Fixed prompt shared by the archived semantic reviews."""
import json

RULE = 'You are an impartial SQLite question-SQL reviewer. Judge only the provided evidence; do not infer hidden facts. Consider query entities, filters, join multiplicity, aggregation units, NULLs, time boundaries, order and top-k. Return exactly one JSON object with only keys "label" and "error_type". label must be supported, incorrect, or insufficient. For supported use error_type none; for insufficient use ambiguous; for incorrect choose scope, aggregation_join, time_order_limit, extra_filter, or other. If the evidence is insufficient use insufficient.'

def prompt(x):
    schema=x['schema']
    if 'Database schema:\n' in schema: schema=schema.split('Database schema:\n',1)[1]
    return RULE+'\n\nSQLite schema:\n'+schema+'\n\nQuestion:\n'+x['question']+'\n\nProposed SQL:\n'+x['sql']
