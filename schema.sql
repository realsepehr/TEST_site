CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS products(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL,category_id INTEGER,
 brand TEXT DEFAULT '',model TEXT DEFAULT '',sku TEXT DEFAULT '',
 short_description TEXT DEFAULT '',description TEXT DEFAULT '',specs TEXT DEFAULT '',
 price REAL DEFAULT 0,sale_price REAL DEFAULT 0,stock INTEGER DEFAULT 0,
 color TEXT DEFAULT '',colors TEXT DEFAULT '',material TEXT DEFAULT '',finish TEXT DEFAULT '',
 length TEXT DEFAULT '',width TEXT DEFAULT '',height TEXT DEFAULT '',weight TEXT DEFAULT '',
 package_dimensions TEXT DEFAULT '',package_weight TEXT DEFAULT '',warranty TEXT DEFAULT '',warranty_company TEXT DEFAULT '',
 shipping_time TEXT DEFAULT '',shipping_cost REAL DEFAULT 0,free_shipping INTEGER DEFAULT 0,
 seo_title TEXT DEFAULT '',seo_description TEXT DEFAULT '',seo_keywords TEXT DEFAULT '',badge TEXT DEFAULT '',
 featured INTEGER DEFAULT 0,new_product INTEGER DEFAULT 0,bestseller INTEGER DEFAULT 0,active INTEGER DEFAULT 1,
 image TEXT DEFAULT '',gallery TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS admin_activity(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,method TEXT NOT NULL,path TEXT NOT NULL,ip TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS page_views(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,path TEXT NOT NULL,ip TEXT DEFAULT '');

INSERT OR IGNORE INTO settings(key,value) VALUES
('site_name','فروشگاه حافظ'),
('tagline','ویترین آنلاین محصولات'),
('phone','09120000000'),
('address','تهران'),
('hero_title','انتخابی حرفه‌ای برای خانه شما'),
('hero_text','محصولات منتخب را در ویترین حافظ ببینید.');

INSERT OR IGNORE INTO categories(name,slug) VALUES
('شیرآلات','faucets'),('سینک','sinks'),('گاز','cookers'),('هود','hoods'),('تجهیزات آشپزخانه','kitchen');
