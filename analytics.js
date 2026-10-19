/* Shared, privacy-minimal measurement for the map and generated content pages.
   Only the exact production hostname sends events. Staging keeps a bounded,
   local diagnostic log; neither GA nor Meta is loaded there. */
(() => {
  const GA = 'G-P7981MBHEF', PIXEL = '1098404802535226';
  const q = new URLSearchParams(location.search);
  try {
    if(q.has('notrack')) {
      if(q.get('notrack') === '0') localStorage.removeItem('fs_notrack');
      else localStorage.setItem('fs_notrack', '1');
    }
  } catch {}
  let excluded = false;
  try { excluded = localStorage.getItem('fs_notrack') === '1'; } catch {}
  const live = location.hostname === 'hkfengshuimap.com';
  const enabled = live && !excluded;
  const path = location.pathname;
  const kind = path.startsWith('/estate/') ? 'estate' : path.startsWith('/district/') ? 'district' : path === '/' || path === '/index.html' ? 'map' : 'content';
  let ref = '';
  try { const r = new URL(document.referrer); if(r.origin !== location.origin && r.hostname !== 'accounts.google.com' && !r.hostname.endsWith('.supabase.co')) ref = r.origin; } catch {}
  const paramsAllowed = new Set(['building_id','estate','district','intent','entry','status','reason','has_hour','after_signin','results','found','source','what','count','mode','how','from','to','edit','people','regions','total_saved','score','grade','now','seconds','buildings','searches','no_result','zoomed_in','saw_intro','saved','shared','opened_nothing','marketing']);
  const clean = p => Object.fromEntries(Object.entries(p || {}).filter(([k,v]) => paramsAllowed.has(k) && ['string','number','boolean'].includes(typeof v)).map(([k,v]) => [k,typeof v === 'string' ? v.slice(0,100) : v]));
  let log = [];
  if(!live) { try { log = JSON.parse(sessionStorage.getItem('fs_tracking_debug') || '[]').slice(-99); } catch {} }
  const track = (event, params = {}) => {
    if(excluded) return;
    const safe = {...clean(params),page_type:kind,environment:live?'production':'staging'};
    if(!live) {
      log.push({event,...safe}); log=log.slice(-100);
      try { sessionStorage.setItem('fs_tracking_debug',JSON.stringify(log)); } catch {}
      const out=document.getElementById('tracking-events'); if(out) out.textContent=JSON.stringify(log,null,2);
    }
    if(enabled && window.gtag) gtag('event',event,safe);
    // Only existing, intentional Meta events; never forward funnel diagnostics,
    // search text, birth fields, names, email, coordinates or OAuth parameters.
    const fb={view_building:'ViewContent',search:'Search',save_building:'AddToWishlist',signin_done:'CompleteRegistration',share:'Share'};
    if(enabled && window.fbq && fb[event]) fbq('track',fb[event],{});
  };
  window.FSTrack = {track,enabled,environment:live?'production':'staging'};
  if(enabled) {
    window.dataLayer=window.dataLayer||[];
    window.gtag=function(){dataLayer.push(arguments);};
    gtag('js',new Date());
    // No query/hash: auth responses and user input cannot leak through page URLs.
    // UTM values are passed separately only on an actual external landing.
    const campaign={};
    if(!document.referrer || ref) for(const [key,out] of [['utm_source','campaign_source'],['utm_medium','campaign_medium'],['utm_campaign','campaign_name']]) {
      const v=q.get(key); if(v && /^[\w .-]{1,80}$/.test(v)) campaign[out]=v;
    }
    gtag('config',GA,{send_page_view:false,page_location:location.origin+path,page_referrer:ref,ignore_referrer:!ref,...campaign});
    const script=document.createElement('script');script.async=true;script.src='https://www.googletagmanager.com/gtag/js?id='+GA;document.head.appendChild(script);
    const fbq=window.fbq=function(){fbq.callMethod?fbq.callMethod.apply(fbq,arguments):fbq.queue.push(arguments);};
    fbq.queue=[];fbq.loaded=true;fbq.version='2.0';window._fbq=fbq;
    // Never initialize the pixel while an auth response remains in the URL.
    if(!q.has('code') && !/access_token|error_description/.test(location.hash)) {
      const pixel=document.createElement('script');pixel.async=true;pixel.src='https://connect.facebook.net/en_US/fbevents.js';document.head.appendChild(pixel);fbq('init',PIXEL);fbq('track','PageView');
    }
  }
  track('page_view');
  if(kind==='estate' || kind==='district') {
    let name='';try{name=decodeURIComponent(path.split('/')[2]||'').replace(/\.html$/,'');}catch{}
    track('content_view',{[kind==='estate'?'estate':'district']:name});
  }
  document.addEventListener('click',e=>{
    const a=e.target.closest('a[data-journey]');if(!a)return;
    const u=new URL(a.href,location.href);
    track('content_to_map',{entry:a.dataset.journey,estate:u.searchParams.get('estate')||'',intent:u.searchParams.get('intent')||'map',building_id:u.searchParams.get('bid')||''});
  });
  document.addEventListener('DOMContentLoaded',()=>{
    if(live || q.get('debug')!=='1')return;
    const details=document.createElement('details');details.style.cssText='position:fixed;bottom:8px;left:8px;z-index:20000;max-width:calc(100% - 16px);background:#fff;color:#222;border:1px solid #999;padding:8px;font:12px monospace;';
    const summary=document.createElement('summary');summary.textContent='測試事件（只留喺本機）';
    const out=document.createElement('pre');out.id='tracking-events';out.style.cssText='max-height:180px;overflow:auto;white-space:pre-wrap';out.textContent=JSON.stringify(log,null,2);
    details.append(summary,out);document.body.appendChild(details);
  });
})();
