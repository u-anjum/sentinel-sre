CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(32) NOT NULL,
    stock INT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(32) NOT NULL,
    qty INT NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO inventory (sku, stock) 
SELECT 'SKU-' || LPAD(g::text, 5, '0'), 1000
FROM generate_series(1, 50000) AS g;