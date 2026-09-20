import os
from urllib.parse import quote
from flask import render_template, request


def register_enhancements(app):
    from app import db
    original_products = app.view_functions.get('products')
    if original_products:
        def products_enhanced():
            q=request.args.get('q','').strip(); cat=request.args.get('cat','').strip(); brand=request.args.get('brand','').strip(); stock=request.args.get('stock','').strip(); sort=request.args.get('sort','featured').strip(); min_price=request.args.get('min_price','').strip(); max_price=request.args.get('max_price','').strip()
            try: min_price_n=float(min_price) if min_price else None
            except ValueError: min_price_n=None
            try: max_price_n=float(max_price) if max_price else None
            except ValueError: max_price_n=None
            c=db()
            sql='SELECT p.*,c.name category,c.slug catslug FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1'; args=[]
            if q: sql+=' AND (p.name LIKE ? OR p.brand LIKE ? OR p.model LIKE ? OR p.sku LIKE ? OR p.description LIKE ? OR p.short_description LIKE ?)'; args += [f'%{q}%']*6
            if cat: sql+=' AND c.slug=?'; args.append(cat)
            if brand: sql+=' AND p.brand=?'; args.append(brand)
            if stock=='available': sql+=' AND p.stock > 0'
            elif stock=='out': sql+=' AND p.stock <= 0'
            price_expr='COALESCE(NULLIF(p.sale_price,0),p.price)'
            if min_price_n is not None: sql+=f' AND {price_expr} >= ?'; args.append(min_price_n)
            if max_price_n is not None: sql+=f' AND {price_expr} <= ?'; args.append(max_price_n)
            order={'price_asc':f'{price_expr} ASC, p.id DESC','price_desc':f'{price_expr} DESC, p.id DESC','name':'p.name COLLATE NOCASE ASC','newest':'p.id DESC','featured':'p.featured DESC,p.bestseller DESC,p.id DESC'}.get(sort,'p.featured DESC,p.bestseller DESC,p.id DESC')
            rows=c.execute(sql+' ORDER BY '+order,args).fetchall(); brands=[r['brand'] for r in c.execute("SELECT DISTINCT brand FROM products WHERE active=1 AND brand<>'' ORDER BY brand").fetchall()]; c.close()
            return render_template('products.html',products=rows,q=q,selected=cat,selected_brand=brand,stock_filter=stock,sort=sort,min_price=min_price,max_price=max_price,brands=brands)
        app.view_functions['products']=products_enhanced
    original_product=app.view_functions.get('product')
    if original_product:
        def product_enhanced(slug):
            c=db()
            p=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.slug=? AND p.active=1',(slug,)).fetchone()
            if not p: c.close(); return original_product(slug)
            related=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 AND p.id<>? AND (p.category_id=? OR (p.brand<>\'\' AND p.brand=?)) ORDER BY (p.category_id=?) DESC,p.featured DESC,p.id DESC LIMIT 6',(p['id'],p['category_id'],p['brand'],p['category_id'])).fetchall()
            if len(related)<6:
                existing={r['id'] for r in related}; extra=c.execute('SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 AND p.id<>? ORDER BY p.featured DESC,p.id DESC LIMIT 12',(p['id'],)).fetchall(); related=related+[r for r in extra if r['id'] not in existing][:6-len(related)]
            c.close(); return render_template('product.html',product=p,related_products=related)
        app.view_functions['product']=product_enhanced
    @app.route('/compare')
    def compare():
        raw=request.args.get('ids',''); ids=[]
        for x in raw.split(','):
            try:
                n=int(x)
                if n>0 and n not in ids: ids.append(n)
            except ValueError: pass
        ids=ids[:4]; c=db(); products=[]
        if ids:
            placeholders=','.join('?' for _ in ids); rows=c.execute(f'SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1 AND p.id IN ({placeholders})',ids).fetchall(); byid={p['id']:p for p in rows}; products=[byid[i] for i in ids if i in byid]
        c.close(); return render_template('compare.html',products=products)
    @app.template_global('whatsapp_url')
    def whatsapp_url(product):
        c=db(); row=c.execute("SELECT value FROM settings WHERE key='phone'").fetchone(); c.close(); phone=''.join(ch for ch in (row[0] if row else '') if ch.isdigit())
        if phone.startswith('0'): phone='98'+phone[1:]
        text=quote(f'سلام، درباره محصول «{product["name"]}» درخواست استعلام قیمت و موجودی دارم.')
        return f'https://wa.me/{phone}?text={text}' if phone else f'https://wa.me/?text={text}'
