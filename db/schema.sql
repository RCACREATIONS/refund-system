CREATE TABLE IF NOT EXISTS customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  status TEXT NOT NULL DEFAULT 'delivered',
  delivered_at DATE NOT NULL,
  total NUMERIC(12,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items (
  id SERIAL PRIMARY KEY,
  order_id TEXT NOT NULL REFERENCES orders(id),
  sku TEXT NOT NULL,
  name TEXT NOT NULL,
  price NUMERIC(12,2) NOT NULL,
  final_sale BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS prior_refunds (
  id SERIAL PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  order_id TEXT REFERENCES orders(id),
  amount NUMERIC(12,2) NOT NULL,
  refunded_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS refund_requests (
  id SERIAL PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  order_id TEXT,
  message TEXT NOT NULL,
  outcome TEXT NOT NULL,
  refund_amount NUMERIC(12,2) NOT NULL,
  customer_reply TEXT NOT NULL,
  review_status TEXT NOT NULL,
  appeal_note TEXT,
  reviewer_note TEXT,
  source TEXT NOT NULL DEFAULT 'user',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  policy_input JSONB,
  policy_result JSONB,
  receipt JSONB
);
CREATE TABLE IF NOT EXISTS audit_events (
  id SERIAL PRIMARY KEY,
  request_id INTEGER NOT NULL REFERENCES refund_requests(id) ON DELETE CASCADE,
  step TEXT NOT NULL,
  detail JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS refund_requests_created_at_idx ON refund_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS audit_events_request_id_idx ON audit_events(request_id);
