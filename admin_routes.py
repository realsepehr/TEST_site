"""Complete admin CRUD routes loaded by the security layer."""
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, abort, send_file
from cloudflare_storage import is_cloudflare, list_media, delete_media
from werkzeug.utils import secure_filename


def register_admin_routes(app):
    # Prevent duplicate registration when the module is initialized more than once
    # (e.g. import/reload paths in the production process).
    if 'admin_products' in app.view_functions:
        return

    def deps():
        from app import db, save_image, UP, unique_slug, slugify, DB
        return db, save_image, UP, unique_slug, slugify, DB

    def guard():
        from flask import session
        return session.get('admin') is True

    @app.route('/admin/products', methods=['GET', 'POST'])
    def admin_products():
        db, save_image, UP, unique_slug, slugify, DB = deps()
        if not guard(): return redirect(url_for('login', next=request.path))
        if request.method=='POST':
            name=request.form.get('name','').strip()
            if not name: flash('نام محصول الزامی است.','error'); return redirect(url_for('admin_products'))
            c=db(); image=''; gallery=[]; primary=request.files.get('image')
            try:
                if primary and primary.filename: image=save_image(primary)
                for f in request.files.getlist('gallery_images'):
                    if f and f.filename: gallery.append(save_image(f))
                c.execute('''INSERT INTO products(name,slug,category_id,brand,model,sku,colors,price,stock,material,warranty,image,gallery,description,active) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)''',(name,unique_slug(c,name),request.form.get('category_id') or None,request.form.get('brand','').strip(),request.form.get('model','').strip(),request.form.get('sku','').strip(),request.form.get('colors','').strip(),float(request.form.get('price') or 0),int(request.form.get('stock') or 0),request.form.get('material','').strip(),request.form.get('warranty','').strip(),image,','.join(gallery),request.form.get('description','').strip()))
                c.commit(); flash('محصول با موفقیت اضافه شد.','success')
            except Exception:
                c.rollback(); raise
            finally: c.close()
            return redirect(url_for('admin_products'))
        q=request.args.get('q','').strip(); stock=request.args.get('stock','')
        c=db(); sql='SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE 1=1'; args=[]
        if q: sql+=' AND (p.name LIKE ? OR p.brand LIKE ? OR p.model LIKE ? OR p.sku LIKE ?)'; args += [f'%{q}%']*4
        if stock=='low': sql+=' AND p.stock BETWEEN 1 AND 5'
        elif stock=='out': sql+=' AND p.stock<=0'
        products=c.execute(sql+' ORDER BY p.id DESC',args).fetchall(); cats=c.execute('SELECT * FROM categories ORDER BY name').fetchall(); c.close()
        return render_template('manage_products.html',products=products,categories=cats,q=q,stock=stock)

    @app.route('/admin/products/edit/<int:pid>', methods=['GET','POST'])
    def admin_product_edit(pid):
        db, save_image, UP, unique_slug, slugify, DB=deps();
        if not guard(): return redirect(url_for('login',next=request.path))
        c=db(); p=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
        if not p: c.close(); abort(404)
        if request.method=='POST':
            name=request.form.get('name','').strip() or p['name']; image=p['image']; gallery=p['gallery'] or ''; f=request.files.get('image')
            if f and f.filename: image=save_image(f)
            gs=[save_image(x) for x in request.files.getlist('gallery_images') if x and x.filename]
            if gs: gallery=','.join([x.strip() for x in gallery.split(',') if x.strip()]+gs)
            c.execute('UPDATE products SET name=?,slug=?,category_id=?,brand=?,model=?,sku=?,colors=?,price=?,stock=?,material=?,warranty=?,image=?,gallery=?,description=? WHERE id=?',(name,unique_slug(c,name,pid),request.form.get('category_id') or None,request.form.get('brand','').strip(),request.form.get('model','').strip(),request.form.get('sku','').strip(),request.form.get('colors','').strip(),float(request.form.get('price') or 0),int(request.form.get('stock') or 0),request.form.get('material','').strip(),request.form.get('warranty','').strip(),image,gallery,request.form.get('description','').strip(),pid)); c.commit(); c.close(); flash('محصول ویرایش شد.','success'); return redirect(url_for('admin_products'))
        cats=c.execute('SELECT * FROM categories ORDER BY name').fetchall(); c.close(); return render_template('product_form.html',p=p,cats=cats)

    @app.route('/admin/products/delete/<int:pid>',methods=['POST'])
    def admin_product_delete(pid):
        db,*_=deps();
        if not guard(): return redirect(url_for('login',next=request.path))
        c=db(); c.execute('DELETE FROM products WHERE id=?',(pid,)); c.commit(); c.close(); flash('محصول حذف شد.','success'); return redirect(url_for('admin_products'))

    @app.route('/admin/categories',methods=['GET','POST'])
    def admin_categories():
        db,*rest=deps(); slugify=rest[2]
        if not guard(): return redirect(url_for('login',next=request.path))
        c=db()
        if request.method=='POST':
            name=request.form.get('name','').strip(); slug=request.form.get('slug','').strip() or slugify(name)
            if name: c.execute('INSERT OR IGNORE INTO categories(name,slug) VALUES(?,?)',(name,slug)); c.commit(); flash('دسته‌بندی اضافه شد.','success')
            c.close(); return redirect(url_for('admin_categories'))
        rows=c.execute('SELECT c.*,COUNT(p.id) product_count FROM categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY c.id ORDER BY c.name').fetchall(); c.close(); return render_template('admin_categories.html',categories=rows)

    @app.route('/admin/categories/delete/<int:cid>',methods=['POST'])
    def admin_category_delete(cid):
        db,*_=deps();
        if not guard(): return redirect(url_for('login',next=request.path))
        c=db(); c.execute('UPDATE products SET category_id=NULL WHERE category_id=?',(cid,)); c.execute('DELETE FROM categories WHERE id=?',(cid,)); c.commit(); c.close(); flash('دسته‌بندی حذف شد.','success'); return redirect(url_for('admin_categories'))

    @app.route('/admin/media',methods=['GET','POST'])
    def admin_media():
        db,save_image,UP,*_=deps()
        if not guard(): return redirect(url_for('login',next=request.path))
        if request.method=='POST':
            f=request.files.get('image')
            if f and f.filename: save_image(f); flash('تصویر آپلود شد.','success')
            return redirect(url_for('admin_media'))
        if is_cloudflare():
            files=list_media('products/')
        else:
            files=[{'name':p.name,'size':p.stat().st_size,'mtime':datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M')} for p in sorted(UP.glob('upload_*'),key=lambda x:x.stat().st_mtime,reverse=True) if p.is_file()]
        return render_template('admin_media.html',files=files)

    @app.route('/admin/media/delete/<path:name>',methods=['POST'])
    def admin_media_delete(name):
        db,save_image,UP,*_=deps();
        if not guard(): return redirect(url_for('login',next=request.path))
        if is_cloudflare():
            delete_media(name)
        else:
            p=(UP/secure_filename(name)).resolve()
            if p.parent==UP.resolve() and p.exists(): p.unlink()
        return redirect(url_for('admin_media'))

    @app.route('/admin/system')
    def admin_system():
        db,*_=deps();
        if not guard(): return redirect(url_for('login',next=request.path))
        from app import UP,DB
        c=db(); data={'products':c.execute('SELECT COUNT(*) n FROM products').fetchone()['n'],'categories':c.execute('SELECT COUNT(*) n FROM categories').fetchone()['n'],'settings':c.execute('SELECT COUNT(*) n FROM settings').fetchone()['n']}; c.close()
        if is_cloudflare():
            media=list_media('products/'); data['uploads_count']=len(media); data['uploads_size']=sum(int(x.get('size',0) or 0) for x in media); data['database_size']=0
        else:
            data['uploads_count']=sum(1 for p in UP.iterdir() if p.is_file()); data['uploads_size']=sum(p.stat().st_size for p in UP.iterdir() if p.is_file()); data['database_size']=DB.stat().st_size if DB.exists() else 0
        return render_template('admin_system.html',data=data)

    @app.route('/admin/backup')
    def admin_backup():
        db,save_image,UP,unique_slug,slugify,DB=deps()
        if not guard(): return redirect(url_for('login',next=request.path))
        if is_cloudflare():
            import json, io
            c=db(); tables=[r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
            payload={t:[dict(r) for r in c.execute(f'SELECT * FROM {t}').fetchall()] for t in tables}; c.close()
            mem=io.BytesIO(json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8'))
            stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); return send_file(mem,as_attachment=True,download_name=f'hafez-d1-backup-{stamp}.json',mimetype='application/json')
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); return send_file(DB,as_attachment=True,download_name=f'hafez-backup-{stamp}.db')

    @app.route('/admin/settings',methods=['GET','POST'])
    def admin_settings():
        db,*_=deps()
        if not guard(): return redirect(url_for('login',next=request.path))
        c=db()
        if request.method=='POST':
            for key in ('site_name','tagline','phone','address','hero_title','hero_text'):
                c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,request.form.get(key,'')))
            c.commit(); flash('تنظیمات ذخیره شد.','success')
        settings={r['key']:r['value'] for r in c.execute('SELECT * FROM settings')}; c.close(); return render_template('admin_settings.html',settings=settings)

    from advanced_admin import register_advanced_admin
    register_advanced_admin(app)
