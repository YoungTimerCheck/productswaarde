-- Run this in the Supabase SQL editor to create all tables.

create table listings (
  id uuid primary key default gen_random_uuid(),
  marktplaats_id text unique,
  title text,
  price numeric,
  price_type text,
  condition text,
  seller_type text,
  location text,
  category text,
  keyword text,
  url text,
  image_url text,
  first_seen timestamp default now(),
  last_seen timestamp default now(),
  status text default 'active',
  days_listed integer default 0
);

create table price_snapshots (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid references listings(id),
  price numeric,
  scraped_at timestamp default now()
);

create table keyword_stats (
  id uuid primary key default gen_random_uuid(),
  keyword text unique,
  avg_price numeric,
  median_price numeric,
  p25_price numeric,
  p75_price numeric,
  total_listings integer,
  active_listings integer,
  last_updated timestamp default now()
);

create table scraper_queue (
  id uuid primary key default gen_random_uuid(),
  keyword text unique,
  added_at timestamp default now(),
  last_scraped timestamp,
  active boolean default true
);

create table alerts (
  id uuid primary key default gen_random_uuid(),
  keyword text,
  max_price numeric,
  email text,
  active boolean default true,
  unsubscribe_token text unique default gen_random_uuid()::text,
  alert_count integer default 0,
  created_at timestamp default now(),
  last_notified timestamp
);
