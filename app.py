import os, sqlite3, uuid, shutil, json, re, time
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, make_response, Response
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from security import init_security
from product_images import request_resolve_async, start_warmup
from cloudflare_storage import get_db as cloud_db, is_cloudflare, put_media, get_media, media_url
BASE=Path(__file__).resolve().parent
DB=BASE/'instance/store.db'
UP=BASE
UP.mkdir(parents=True,exist_ok=True)
DB.parent.mkdir(parents=True,exist_ok=True)
SECRET_KEY=os.getenv('SECRET_KEY') or uuid.uuid4().hex+uuid.uuid4().hex
app=Flask(__name__, static_folder=None, template_folder=str(BASE))
app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=1)
app.secret_key=SECRET_KEY
app.config.update(MAX_CONTENT_LENGTH=10*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','1').lower() in ('1','true','yes'),PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
init_security(app)
ALLOWED_IMAGE_EXT={'jpg','jpeg','png','webp'}; ALLOWED_IMAGE_TYPES={'jpg':b'\xff\xd8\xff','jpeg':b'\xff\xd8\xff','png':b'\x89PNG\r\n\x1a\n','webp':b'RIFF'}
LOGIN_WINDOW=300; LOGIN_LIMIT=8; _login_attempts={}
def db():
    return cloud_db()
def slugify(text):
    text=(text or '').strip().lower(); text=re.sub(r'[^\w\u0600-\u06ff\s-]','',text,flags=re.UNICODE); text=re.sub(r'[\s_-]+','-',text).strip('-'); return text or uuid.uuid4().hex[:10]
def unique_slug(c,name,pid=None):
    base=slugify(name); slug=base; i=2
    while True:
        q='SELECT id FROM products WHERE slug=?'; a=[slug]
        if pid is not None: q+=' AND id<>?'; a.append(pid)
        if not c.execute(q,a).fetchone(): return slug
        slug=f'{base}-{i}'; i+=1
def init_db():
    c=db(); c.executescript('''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL);CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,slug TEXT UNIQUE NOT NULL,category_id INTEGER,brand TEXT DEFAULT '',model TEXT DEFAULT '',sku TEXT DEFAULT '',short_description TEXT DEFAULT '',description TEXT DEFAULT '',specs TEXT DEFAULT '',price REAL DEFAULT 0,sale_price REAL DEFAULT 0,stock INTEGER DEFAULT 0,color TEXT DEFAULT '',colors TEXT DEFAULT '',material TEXT DEFAULT '',finish TEXT DEFAULT '',length TEXT DEFAULT '',width TEXT DEFAULT '',height TEXT DEFAULT '',weight TEXT DEFAULT '',package_dimensions TEXT DEFAULT '',package_weight TEXT DEFAULT '',warranty TEXT DEFAULT '',warranty_company TEXT DEFAULT '',shipping_time TEXT DEFAULT '',shipping_cost REAL DEFAULT 0,free_shipping INTEGER DEFAULT 0,seo_title TEXT DEFAULT '',seo_description TEXT DEFAULT '',seo_keywords TEXT DEFAULT '',badge TEXT DEFAULT '',featured INTEGER DEFAULT 0,new_product INTEGER DEFAULT 0,bestseller INTEGER DEFAULT 0,active INTEGER DEFAULT 1,image TEXT DEFAULT '',gallery TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
    for k,v in {'site_name':'فروشگاه حافظ','tagline':'ویترین آنلاین محصولات','phone':'09120000000','address':'تهران','hero_title':'انتخابی حرفه‌ای برای خانه شما','hero_text':'محصولات منتخب را در ویترین حافظ ببینید.'}.items(): c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,v))
    if c.execute('SELECT COUNT(*) n FROM categories').fetchone()['n']==0:
        for n,s in [('شیرآلات','faucets'),('سینک','sinks'),('گاز','cookers'),('هود','hoods'),('تجهیزات آشپزخانه','kitchen')]: c.execute('INSERT INTO categories(name,slug) VALUES(?,?)',(n,s))
    c.commit(); c.close()
def migrate():
    c=db(); cols={r['name'] for r in c.execute('PRAGMA table_info(products)')}; additions={'model':'TEXT DEFAULT ""','sku':'TEXT DEFAULT ""','short_description':'TEXT DEFAULT ""','price':'REAL DEFAULT 0','sale_price':'REAL DEFAULT 0','stock':'INTEGER DEFAULT 0','color':'TEXT DEFAULT ""','colors':'TEXT DEFAULT ""','material':'TEXT DEFAULT ""','finish':'TEXT DEFAULT ""','length':'TEXT DEFAULT ""','width':'TEXT DEFAULT ""','height':'TEXT DEFAULT ""','weight':'TEXT DEFAULT ""','package_dimensions':'TEXT DEFAULT ""','package_weight':'TEXT DEFAULT ""','warranty':'TEXT DEFAULT ""','warranty_company':'TEXT DEFAULT ""','shipping_time':'TEXT DEFAULT ""','shipping_cost':'REAL DEFAULT 0','free_shipping':'INTEGER DEFAULT 0','seo_title':'TEXT DEFAULT ""','seo_description':'TEXT DEFAULT ""','seo_keywords':'TEXT DEFAULT ""','badge':'TEXT DEFAULT ""','new_product':'INTEGER DEFAULT 0','bestseller':'INTEGER DEFAULT 0','gallery':'TEXT DEFAULT ""'}
    for k,v in additions.items():
        if k not in cols: c.execute(f'ALTER TABLE products ADD COLUMN {k} {v}')
    c.commit(); c.close()
def client_key(): return request.headers.get('X-Forwarded-For',request.remote_addr or 'unknown').split(',')[0].strip()
def rate_limited(key):
    now=time.time(); arr=[t for t in _login_attempts.get(key,[]) if now-t<LOGIN_WINDOW]; _login_attempts[key]=arr; return len(arr)>=LOGIN_LIMIT
def record_login_failure(key): _login_attempts.setdefault(key,[]).append(time.time())
def clear_login_failures(key): _login_attempts.pop(key,None)
def valid_image(file):
    if not file or not file.filename:return False
    name=secure_filename(file.filename); ext=name.rsplit('.',1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED_IMAGE_EXT:return False
    head=file.stream.read(12);file.stream.seek(0)
    if ext in ('jpg','jpeg','png') and not head.startswith(ALLOWED_IMAGE_TYPES[ext]):return False
    if ext=='webp' and not(head.startswith(b'RIFF') and head[8:12]==b'WEBP'):return False
    return True
def save_image(file):
    if not valid_image(file):
        raise ValueError('فرمت تصویر مجاز نیست.')
    if is_cloudflare():
        return put_media(file)
    name=secure_filename(file.filename);ext=name.rsplit('.',1)[-1].lower();stem=secure_filename(name.rsplit('.',1)[0]) or 'product';fn=f'upload_{stem}_{uuid.uuid4().hex[:12]}.{ext}';file.save(UP/fn);return fn

def safe_next(value): return value if value and value.startswith('/') and not value.startswith('//') else url_for('admin_home')
def product_image_src(product):
    image=(product['image'] or '').strip() if product else ''
    if image.startswith('http://') or image.startswith('https://'): return image
    if image: return media_url(image) if is_cloudflare() else '/static/uploads/'+image
    return '/product-image/'+str(product['id']) if product and product['id'] else ''
if not is_cloudflare():
    init_db();migrate()
@app.route('/static/<path:filename>', endpoint='static')
def static_file(filename):
    if is_cloudflare():
        from pyodide.ffi import run_sync
        assets = request.environ['workers.env'].ASSETS
        # Flat layout: CSS/JS/upload assets live at repository root.
        asset_name = filename
        if asset_name.startswith('uploads/'):
            asset_name = asset_name.split('/', 1)[1]
        asset_response = run_sync(assets.fetch(f'https://assets.local/{asset_name}'))
        body = run_sync(asset_response.bytes())
        data = body.to_py() if hasattr(body, 'to_py') else body
        headers = asset_response.headers.to_py() if hasattr(asset_response.headers, 'to_py') else dict(asset_response.headers)
        return Response(bytes(data), status=asset_response.status, headers=headers)
    local = BASE / (filename.split('/',1)[1] if filename.startswith('uploads/') else filename.split('/')[-1])
    if not local.is_file(): abort(404)
    return send_file(local)

@app.template_global('product_image_src')
def _product_image_src(product): return product_image_src(product)
@app.template_global('media_url')
def _media_url(key): return media_url(key) if key else ''
@app.route('/media/<path:key>')
def media_file(key):
    if is_cloudflare():
        payload = get_media(key)
        if not payload: abort(404)
        data, mimetype = payload
        return Response(data, status=200, mimetype=mimetype, headers={'Cache-Control':'public, max-age=31536000, immutable'})
    local = UP / os.path.basename(key)
    if not local.is_file(): abort(404)
    return send_file(local)

@app.route('/product-image/<int:product_id>')
def product_image(product_id):
    c=db();p=c.execute('SELECT id,image FROM products WHERE id=? AND active=1',(product_id,)).fetchone();c.close()
    if not p: abort(404)
    image=(p['image'] or '').strip()
    if image.startswith('http://') or image.startswith('https://'): return redirect(image,code=302)
    if image:
        if is_cloudflare():
            payload = get_media(image)
            if payload:
                data, mimetype = payload
                return Response(data, status=200, mimetype=mimetype, headers={'Cache-Control':'public, max-age=31536000, immutable'})
        else:
            local=UP/os.path.basename(image)
            if local.is_file():
                response=make_response(send_file(local)); response.headers['Cache-Control']='public, max-age=86400'; return response
    if not is_cloudflare():
        request_resolve_async(str(DB), product_id)
    return Response(b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" viewBox="0 0 1 1"><rect width="1" height="1" fill="none"/></svg>', status=200, mimetype='image/svg+xml', headers={'Cache-Control':'no-store'})
@app.after_request
def security_headers(response):
    response.headers.setdefault('X-Content-Type-Options','nosniff');response.headers.setdefault('X-Frame-Options','SAMEORIGIN');response.headers.setdefault('Referrer-Policy','strict-origin-when-cross-origin');response.headers.setdefault('Permissions-Policy','camera=(), microphone=(), geolocation=()')
    if request.is_secure:response.headers.setdefault('Strict-Transport-Security','max-age=31536000; includeSubDomains')
    return response
@app.before_request
def protect_admin_requests():
    if request.path.startswith('/admin/') and request.path!='/admin/login' and request.method in {'POST','PUT','PATCH','DELETE'}:
        origin=request.headers.get('Origin');referer=request.headers.get('Referer');host=request.host_url.rstrip('/')
        if origin and origin.rstrip('/')!=host:abort(403)
        if not origin and referer and not referer.startswith(host+'/'):abort(403)
@app.context_processor
def ctx():
    c=db();cats=c.execute('SELECT * FROM categories ORDER BY name').fetchall();c.close();c2=db();s={r['key']:r['value'] for r in c2.execute('SELECT * FROM settings')};c2.close();return {'settings':s,'nav_categories':cats}
def admin(f):
    @wraps(f)
    def w(*a,**k):return f(*a,**k) if session.get('admin') is True else redirect(url_for('login',next=request.path))
    return w
@app.route('/')
def home():
    c=db();p=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 ORDER BY p.featured DESC,p.bestseller DESC,p.id DESC LIMIT 12').fetchall();cats=c.execute('SELECT c.*,COUNT(p.id) count FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id').fetchall();c.close();return render_template('index.html',products=p,categories=cats)
@app.route('/products')
def products():
    q=request.args.get('q','').strip();cat=request.args.get('cat','');c=db();sql='SELECT p.*,c.name category,c.slug catslug FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1';a=[]
    if q:sql+=' AND (p.name LIKE ? OR p.brand LIKE ? OR p.model LIKE ? OR p.sku LIKE ? OR p.description LIKE ?)';a += [f'%{q}%']*5
    if cat:sql+=' AND c.slug=?';a.append(cat)
    rows=c.execute(sql+' ORDER BY p.featured DESC,p.bestseller DESC,p.id DESC',a).fetchall();c.close();return render_template('products.html',products=rows,q=q,selected=cat)
@app.route('/product/<slug>')
def product(slug):
    c=db();p=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.slug=? AND p.active=1',(slug,)).fetchone();c.close();return render_template('product.html',product=p) if p else abort(404)
@app.route('/admin/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        key=client_key()
        if rate_limited(key):flash('تعداد تلاش‌های ورود زیاد است. چند دقیقه بعد دوباره تلاش کنید.','error');return render_template('login.html'),429
        username=os.getenv('ADMIN_USERNAME');password=os.getenv('ADMIN_PASSWORD')
        if username and password and request.form.get('username')==username and request.form.get('password')==password:
            clear_login_failures(key);session.clear();session.permanent=True;session['admin']=True;return redirect(safe_next(request.args.get('next')))
        record_login_failure(key);flash('نام کاربری یا رمز عبور اشتباه است.','error')
    return render_template('login.html')

# Private-looking admin entry URL. It shows the same secure admin login form,
# but after successful authentication it opens the admin dashboard.
@app.route('/admin/login/admin/sepehr/login',methods=['GET','POST'])
def sepehr_admin_login():
    if session.get('admin') is True:
        return redirect(url_for('admin_home'))
    if request.method=='POST':
        key=client_key()
        if rate_limited(key):
            flash('تعداد تلاش‌های ورود زیاد است. چند دقیقه بعد دوباره تلاش کنید.','error')
            return render_template('login.html'),429
        username=os.getenv('ADMIN_USERNAME');password=os.getenv('ADMIN_PASSWORD')
        if username and password and request.form.get('username')==username and request.form.get('password')==password:
            clear_login_failures(key);session.clear();session.permanent=True;session['admin']=True
            return redirect(url_for('admin_home'))
        record_login_failure(key);flash('نام کاربری یا رمز عبور اشتباه است.','error')
    return render_template('login.html')
@app.route('/admin/logout')
def logout():session.clear();return redirect(url_for('home'))
@app.route('/admin')
@admin
def admin_home():
    c=db();counts={k:c.execute(q).fetchone()['n'] for k,q in {'products':'SELECT COUNT(*) n FROM products','categories':'SELECT COUNT(*) n FROM categories','featured':'SELECT COUNT(*) n FROM products WHERE featured=1'}.items()};c.close();return render_template('admin.html',counts=counts)
from admin_routes import register_admin_routes
register_admin_routes(app)
from enhancements import register_enhancements
app.config['STORE_PHONE']=os.getenv('STORE_PHONE','')
register_enhancements(app)

@app.route('/hafez-panel')
def hafez_panel():
    return redirect(url_for('admin_home')) if session.get('admin') is True else redirect(url_for('login', next='/hafez-panel'))

@app.route('/hafez-panel/login')
def hafez_panel_login():
    return redirect(url_for('login', next='/hafez-panel'))

@app.route('/hafez-panel/<section>')
def hafez_panel_section(section):
    allowed={'products':'admin_products','categories':'admin_categories','media':'admin_media','system':'admin_system','backup':'admin_backup','settings':'admin_settings'}
    endpoint=allowed.get(section)
    if not endpoint: abort(404)
    return redirect(url_for(endpoint))

if not is_cloudflare():
    start_warmup(str(DB))