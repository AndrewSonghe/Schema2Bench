CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT, city TEXT);
CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(customer_id), amount REAL, status TEXT);
INSERT INTO customers VALUES (1, 'Ada', 'York'), (2, 'Ben', 'Bath'), (3, 'Clara', 'York');
INSERT INTO orders VALUES (1, 1, 40.0, 'paid'), (2, 1, 25.0, 'paid'), (3, 2, 90.0, 'open'), (4, 3, 15.0, 'paid');
