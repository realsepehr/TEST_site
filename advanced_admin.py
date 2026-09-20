"""Advanced security, analytics, UX and backup features for the admin panel."""
import os, io, zipfile, hmac, hashlib, base64, struct, time, json
from datetime import datetime
from flask import render_template, request, redirect, url_for, session, flash, send_file, abort


def _guard():
    return session.get('admin') is True


def _db():
    from app import db
    return db()


def _totp(secret, counter):
    key=base64.b32decode(secret.replace(' ','').upper() + '='*((8-len(secret.replace(' ','').upper())%8)%8))
    msg=struct.pack('>Q', counter)
    digest=hmac.new(key,msg,hashlib.sha1).digest()
    off=digest[-1]&15
    return str((struct.unpack('>I',digest[off:off+4])[0]&0x7fffffff)%1000000).zfill(6)


def _totp_ok(secret, code):
    if not secret or not code or not code.isdigit() or len(code)!=6: return False
    now=int(time.time())//30
    return any(hmac.compare_digest(_totp(secret,now+i),code) for i in (-1,0,1))


def register_advanced_admin(app):
    @app.before_request
    def advanced_admin_security():
        if request.path.startswith('/admin') and request.path != '/admin/login' and _guard():
            # Optional TOTP: activate by setting ADMIN_2FA_SECRET in Railway.
            if os.getenv('ADMIN_2FA_SECRET') and not session.get('admin_2fa') and request.path != '/admin/2fa':
                return redirect(url_for('admin_2fa', next=request.path))
            if request.method in {'POST','PUT','PATCH','DELETE'}:
                try:
                    c=_db(); c.execute('CREATE TABLE IF NOT EXISTS admin_activity(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,method TEXT NOT NULL,path TEXT NOT NULL,ip TEXT DEFAULT "")'); c.execute('INSERT INTO admin_activity(at,method,path,ip) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),request.method,request.path,request.remote_addr or '')); c.commit(); c.close()
                except Exception: pass

    @app.route('/admin/2fa', methods=['GET','POST'])
    def admin_2fa():
        if not _guard(): return redirect(url_for('login', next=request.path))
        secret=os.getenv('ADMIN_2FA_SECRET','').replace(' ','').upper()
        if not secret: session['admin_2fa']=True; return redirect(request.args.get('next') or url_for('admin_home'))
        if request.method=='POST':
            if _totp_ok(secret,request.form.get('code','').strip()): session['admin_2fa']=True; return redirect(request.args.get('next') or url_for('admin_home'))
            flash('کد تأیید دو مرحله‌ای نادرست است.','error')
        return render_template('admin_2fa.html',next=request.args.get('next',''))

    @app.route('/admin/security')
    def admin_security():
        if not _guard(): return redirect(url_for('login', next=request.path))
        c=_db(); c.execute('CREATE TABLE IF NOT EXISTS admin_activity(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,method TEXT NOT NULL,path TEXT NOT NULL,ip TEXT DEFAULT "")'); rows=c.execute('SELECT * FROM admin_activity ORDER BY id DESC LIMIT 100').fetchall(); c.close()
        return render_template('admin_security.html',rows=rows,twofa=bool(os.getenv('ADMIN_2FA_SECRET')))

    @app.route('/admin/analytics')
    def admin_analytics():
        if not _guard(): return redirect(url_for('login', next=request.path))
        c=_db();
        c.execute('CREATE TABLE IF NOT EXISTS page_views(id INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT NOT NULL,path TEXT NOT NULL,ip TEXT DEFAULT "")')
        top=c.execute('SELECT path,COUNT(*) n FROM page_views GROUP BY path ORDER BY n DESC LIMIT 10').fetchall(); recent=c.execute('SELECT COUNT(*) n FROM page_views WHERE at>=datetime("now","-7 day")').fetchone()['n']; products=c.execute('SELECT id,name,stock FROM products ORDER BY stock ASC,id DESC LIMIT 10').fetchall(); c.close()
        return render_template('admin_analytics.html',top=top,recent=recent,products=products)

    @app.route('/admin/backup/full')
    def admin_full_backup():
        if not _guard(): return redirect(url_for('login', next=request.path))
        from app import DB, UP, db
        from cloudflare_storage import is_cloudflare, list_media
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); mem=io.BytesIO()
        if is_cloudflare():
            c=db(); tables=[r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
            payload={t:[dict(r) for r in c.execute(f'SELECT * FROM {t}').fetchall()] for t in tables}; c.close()
            media=list_media('products/')
            with zipfile.ZipFile(mem,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr('d1-data.json', json.dumps(payload,ensure_ascii=False,indent=2))
                z.writestr('r2-media-manifest.json', json.dumps(media,ensure_ascii=False,indent=2))
            mem.seek(0); return send_file(mem,as_attachment=True,download_name=f'hafez-cloudflare-backup-{stamp}.zip',mimetype='application/zip')
        with zipfile.ZipFile(mem,'w',zipfile.ZIP_DEFLATED) as z:
            if DB.exists(): z.write(DB,'store.db')
            for p in UP.rglob('*'):
                if p.is_file(): z.write(p, 'uploads/'+p.relative_to(UP).as_posix())
        mem.seek(0); return send_file(mem,as_attachment=True,download_name=f'hafez-full-backup-{stamp}.zip',mimetype='application/zip')

    @app.route('/admin/sessions')
    def admin_sessions():
        if not _guard(): return redirect(url_for('login', next=request.path))
        return render_template('admin_sessions.html')
