(()=>{
const root=document.documentElement,toggle=document.getElementById('themeToggle');
const $$=(s,p=document)=>[...p.querySelectorAll(s)];
const style=document.createElement('style');
style.textContent=`@media(max-width:700px){.site-header{background:#d9d9d9!important;color:#181a1e!important;border-bottom-color:#c5c5c5!important}.site-header .brand,.site-header .desktop-nav a{color:#181a1e!important}.site-header .icon-btn{background:#cecece!important;color:#202328!important;border-color:#bdbdbd!important}.hafez-dark .site-header{background:#292b2f!important;color:#f3f4f6!important;border-bottom-color:#393c42!important}.hafez-dark .site-header .brand,.hafez-dark .desktop-nav a{color:#f3f4f6!important}.hafez-dark .site-header .icon-btn{background:#34373c!important;color:#f3d98f!important;border-color:#464950!important}}`;
document.head.appendChild(style);
$$('img').forEach(i=>{i.loading='lazy';i.decoding='async'});
if(localStorage.getItem('hafez-theme')==='dark')root.classList.add('hafez-dark');
const sync=()=>{if(toggle){toggle.textContent=root.classList.contains('hafez-dark')?'☀':'☾';toggle.title=root.classList.contains('hafez-dark')?'حالت روشن':'حالت تاریک'}};
sync();
toggle?.addEventListener('click',()=>{root.classList.toggle('hafez-dark');localStorage.setItem('hafez-theme',root.classList.contains('hafez-dark')?'dark':'light');sync()});
const ADMIN_PUBLIC='/manage-7f4c9b2d6e8a1f5c3b9d';
const toPrivate=(value)=>{if(!value)return value;try{const u=new URL(value,location.origin);if(u.origin===location.origin&&u.pathname==='/admin')return ADMIN_PUBLIC+(u.search||'')+(u.hash||'');if(u.origin===location.origin&&u.pathname.startsWith('/admin/'))return ADMIN_PUBLIC+u.pathname.slice(6)+(u.search||'')+(u.hash||'')}catch(e){}return value};
const rewriteAdminUrls=()=>{document.querySelectorAll('a[href],form[action]').forEach(el=>{const attr=el.tagName==='FORM'?'action':'href';const value=el.getAttribute(attr);const next=toPrivate(value);if(next!==value)el.setAttribute(attr,next)});};
rewriteAdminUrls();
document.addEventListener('click',e=>{const a=e.target.closest?.('a[href]');if(!a)return;const value=a.getAttribute('href'),next=toPrivate(value);if(next!==value)a.setAttribute('href',next)},true);
document.addEventListener('submit',e=>{const f=e.target;if(!(f instanceof HTMLFormElement))return;const next=toPrivate(f.getAttribute('action')||location.pathname);if(next!==f.getAttribute('action'))f.setAttribute('action',next)},true);

// Store navigation: one button that opens the device's available map/navigation apps.
const STORE_LAT='30.2683362';
const STORE_LNG='57.0654670';
const STORE_NAME='فروشگاه حافظ';
const GOOGLE_MAP_URL=`https://www.google.com/maps/dir/?api=1&destination=${STORE_LAT},${STORE_LNG}`;
const addStoreNavigation=()=>{
 const home=document.querySelector('.hafez-home');
 if(!home||document.getElementById('storeNavigation'))return;
 const section=document.createElement('section');
 section.id='storeNavigation';section.className='store-navigation wrap';
 section.innerHTML=`<div class="store-nav-card"><div class="store-nav-copy"><span class="eyebrow">STORE LOCATION</span><h2>مسیریابی تا فروشگاه</h2><p>برای رفتن به فروشگاه، مسیریابی را بزنید تا برنامه‌های مسیریابی موجود روی گوشی شما باز شوند.</p><small>مقصد: ${STORE_LAT}, ${STORE_LNG}</small></div><button class="store-nav-trigger" type="button"><span>مسیریابی تا فروشگاه</span><b>←</b></button></div>`;
 const intro=home.querySelector('.intro-modern');
 if(intro)intro.insertAdjacentElement('afterend',section);else home.prepend(section);
 const trigger=section.querySelector('.store-nav-trigger');
 trigger.addEventListener('click',()=>{
   const isAndroid=/Android/i.test(navigator.userAgent);
   const isIOS=/iPhone|iPad|iPod/i.test(navigator.userAgent);
   if(isAndroid){
     // geo: opens the Android system chooser when several navigation apps are installed.
     const geo=`geo:${STORE_LAT},${STORE_LNG}?q=${STORE_LAT},${STORE_LNG}(${encodeURIComponent(STORE_NAME)})`;
     window.location.href=geo;
     setTimeout(()=>{window.location.href=GOOGLE_MAP_URL},1200);
   }else if(isIOS){
     const apple=`maps://?daddr=${STORE_LAT},${STORE_LNG}`;
     window.location.href=apple;
     setTimeout(()=>{window.location.href=GOOGLE_MAP_URL},1200);
   }else{
     window.open(GOOGLE_MAP_URL,'_blank','noopener,noreferrer');
   }
 });
};
addStoreNavigation();
const navStyle=document.createElement('style');
navStyle.textContent=`.store-navigation{padding:18px 0 10px}.store-nav-card{position:relative;overflow:hidden;background:linear-gradient(135deg,#171b24,#0d1016);border:1px solid #2d323d;border-radius:22px;padding:24px;box-shadow:0 18px 50px #00000016}.store-nav-card:before{content:"";position:absolute;width:230px;height:230px;border:1px solid #d8b76f22;border-radius:50%;left:-90px;bottom:-150px}.store-nav-copy{position:relative;z-index:1}.store-nav-copy .eyebrow{color:#c8a45d}.store-nav-copy h2{margin:8px 0 6px;color:#f7f3e9;font-size:24px}.store-nav-copy p{margin:0;color:#aeb4bf;font-size:11px;line-height:1.9}.store-nav-copy small{display:block;margin-top:10px;color:#d8b76f;font-size:9px}.store-nav-trigger{margin-top:18px;width:100%;display:flex;justify-content:space-between;align-items:center;border:1px solid #3a3f49;border-radius:13px;background:#e2c77f;color:#15181d;padding:13px 16px;font:inherit;font-size:11px;font-weight:900;cursor:pointer;transition:.2s}.store-nav-trigger:hover{transform:translateY(-2px);box-shadow:0 12px 30px #d8b76f25}.store-nav-trigger b{font-size:15px}@media(max-width:700px){.store-navigation{padding:12px 0 8px}.store-nav-card{padding:19px;border-radius:18px}.store-nav-copy h2{font-size:20px}.store-nav-trigger{font-size:10px;min-height:58px}}`;
document.head.appendChild(navStyle);
const progress=document.createElement('div');progress.className='hafez-progress';document.body.appendChild(progress);const progressUpdate=()=>{let m=document.documentElement.scrollHeight-innerHeight;progress.style.width=(m>0?scrollY/m*100:0)+'%'};addEventListener('scroll',progressUpdate,{passive:true});progressUpdate();
})();