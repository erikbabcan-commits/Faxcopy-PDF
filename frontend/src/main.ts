import {api, ApiError, setCsrf} from './api.js';
import {badge, bytes, empty, esc, icon, jobTable, labels, number, time, toast} from './ui.js';
import type {Assistant, Audit, Job, Key, Me, Page, Profile, Rules, Stats, User} from './types.js';

const app = document.getElementById('app')!;
const modal = document.getElementById('modal') as HTMLDialogElement;
let me: Me | null = null;
let profiles: Profile[] = [];
let stats: Stats | null = null;
let currentJob: Job | null = null;
let generation = 0;
let query = '';
let statusFilter = '';
let offset = 0;
let busy = false;
let uploadFile: File | null = null;
let uploadKey = '';
let uploadMetadata = '';
let previousFocus: HTMLElement | null = null;
let editingProfile: Profile | undefined;
const canWrite = (): boolean => me?.user.role === 'owner' || me?.user.role === 'operator';
const owner = (): boolean => me?.user.role === 'owner';
const roleLabel = (role: string): string => ({owner: 'Vlastník', operator: 'DTP operátor', viewer: 'Pozorovateľ'}[role] || role);
const route = (): string => location.hash.slice(1) || 'home';
const latestProfiles = (): Profile[] => profiles.filter(p => !profiles.some(x => x.family_id === p.family_id && x.version > p.version));
function errorMessage(error: unknown): string {return error instanceof Error ? error.message : 'Operáciu sa nepodarilo dokončiť.';}
function fail(error: unknown): void {
  if (error instanceof ApiError && error.status === 401) {me = null; setCsrf(''); modal.close(); renderLogin();}
  toast(errorMessage(error), true);
}
function loginHint(): string {try {return localStorage.getItem('pp_workspace_id') || '';} catch {return '';}}
function renderLogin(): void {
  document.title = 'Prihlásenie · PressPilot';
  app.innerHTML = `<main id="main" class="login-screen"><section class="login-story"><a class="brand" href="#home"><span class="brand-mark">P<span>↗</span></span>PressPilot<span class="brand-ai">DTP</span></a><div class="login-copy"><span class="eyebrow light">VAŠE NOVÉ DTP PRACOVISKO</span><h1>Menej kontroly.<br>Viac istoty.</h1><p>PDF, výrobný profil a jasný ďalší krok.<br>Technická kontrola, ktorá pomáha ľuďom —<br>nenahrádza ich úsudok.</p><div class="paper-art" aria-hidden="true"><div class="paper-back"></div><div class="paper-front"><span>PRESSPILOT / INSPECT</span><strong>Good print<br>starts here.</strong><div class="paper-line"></div><small>01 — TECHNICKÁ KONTROLA</small></div><span class="paper-check">${icon('check')}</span></div></div><p class="login-foot">Základná kontrola PDF · Bez automatického uvoľnenia do tlače</p></section><section class="login-form-wrap"><div class="login-form"><span class="eyebrow">VITAJTE SPÄŤ</span><h2>Vaše pracovisko.</h2><p class="muted">Prihláste sa a pokračujte v predtlačovej príprave.</p><form id="login-form"><label>ID pracoviska<input name="workspace_id" value="${esc(loginHint())}" required minlength="36" maxlength="36" autocomplete="organization" placeholder="UUID pridelené správcom"></label><label>E-mail<input name="email" type="email" required autocomplete="username" placeholder="meno@tlaciaren.sk"></label><label>Heslo<input name="password" type="password" required maxlength="256" autocomplete="current-password" placeholder="Vaše heslo"></label><p class="form-error" role="alert"></p><button class="btn primary full" type="submit">Prihlásiť sa ${icon('arrow')}</button></form><p class="login-help">Prvé pracovisko vytvorí správca príkazom<br><code>python -m app.manage bootstrap</code>.<br>Nie je tu predvolené heslo ani verejná registrácia.</p></div></section></main>`;
}
function shell(content: string, view: string): void {
  if (!me) return;
  const items = [['home','grid','Prehľad'], ['jobs','file','Zákazky'], ['profiles','sliders','Výrobné profily'], ['audit','clock','Auditná stopa'], ['settings','settings','Nastavenia']];
  const title = view.startsWith('job/') ? 'Detail zákazky' : items.find(x => x[0] === view)?.[2] || 'Prehľad';
  document.title = `${title} · PressPilot`;
  app.innerHTML = `<div class="workspace"><aside class="sidebar"><a class="brand" href="#home"><span class="brand-mark">P<span>↗</span></span>PressPilot</a><div class="workspace-switch"><span class="workspace-letter">${esc(me.workspace.name.slice(0,1).toUpperCase())}</span><div><strong>${esc(me.workspace.name)}</strong><small>Pracovisko · ${esc(me.workspace.plan)}</small></div><span class="workspace-caret">⌄</span></div><span class="nav-caption">PRACOVISKO</span><nav aria-label="Hlavná navigácia">${items.map(([id, glyph, text]) => `<a href="#${id}" class="nav-item ${view === id || id === 'jobs' && view.startsWith('job/') ? 'active' : ''}" ${view === id ? 'aria-current="page"' : ''}>${icon(glyph!)}<span>${text}</span>${id === 'jobs' && stats?.pending_review ? `<span class="nav-count">${stats.pending_review}</span>` : ''}</a>`).join('')}</nav><div class="sidebar-bottom"><div class="boundary-note">${icon('shield')}<strong>Človek má posledné slovo.</strong><p>MVP kontroluje vybrané parametre. Uvoľnenie do výroby zostáva mimo systému.</p><span>BASIC INSPECTION · v${esc(me.capabilities.version)}</span></div><div class="sidebar-user"><span class="avatar">${esc(me.user.email.slice(0,2).toUpperCase())}</span><div><strong>${esc(me.user.email)}</strong><small>${roleLabel(me.user.role)}</small></div><button class="icon-btn" data-action="logout" aria-label="Odhlásiť sa">${icon('logout')}</button></div></div></aside><div class="page"><header class="topbar"><button class="icon-btn mobile-menu" data-action="menu" aria-label="Zobraziť navigáciu">${icon('menu')}</button><div class="breadcrumb">Pracovisko <span>/</span> <strong>${title}</strong></div><div class="topbar-right"><span class="worker-status ${stats?.worker_online ? 'online' : ''}"><span class="dot"></span>${stats?.worker_online ? 'Worker je pripojený' : 'Worker nie je potvrdený'}</span><span class="topbar-divider"></span><span class="avatar small">${esc(me.user.email.slice(0,2).toUpperCase())}</span></div></header><main id="main" tabindex="-1">${content}</main><footer class="page-footer"><span>PressPilot · Kontrola s kontextom.</span><span>Originál nemeníme. Výsledky verzujeme.</span></footer></div></div>`;
}
function heading(kicker: string, title: string, subtitle: string, action = ''): string {
  return `<div class="page-heading"><div><span class="eyebrow">${esc(kicker)}</span><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>${action}</div>`;
}
function uploadButton(): string {return canWrite() ? `<button class="btn primary" data-action="upload">${icon('plus')} Nová kontrola</button>` : '';}
function overview(s: Stats, jobs: Job[]): string {
  const max = Math.max(1, ...s.daily.map(d => d.count));
  return `${heading('KONTROLNÉ CENTRUM', 'Každý podklad pod kontrolou.', 'Dobrá tlač začína správnymi dátami. Tu máte prehľad o tých vašich.', uploadButton())}<div class="hero-band"><div><span class="eyebrow light">OD PODKLADU K ROZHODNUTIU</span><h2>Rutinu kontroluje systém.<br>O výsledku rozhodujete vy.</h2><p>Nahrajte PDF. Vyberte výrobný profil.<br>Dostaňte konkrétne nálezy, nie neurčitý odhad.</p><a class="text-link light" href="#profiles">Pozrieť výrobné profily ${icon('arrow')}</a></div><div class="flow-art" aria-label="PDF, kontrola, DTP posúdenie"><div class="flow-step">${icon('file')}<strong>01</strong><span>PDF podklad</span></div><span class="flow-arrow">→</span><div class="flow-step highlighted">${icon('sliders')}<strong>02</strong><span>Kontrola</span></div><span class="flow-arrow">→</span><div class="flow-step">${icon('users')}<strong>03</strong><span>DTP posúdenie</span></div></div></div><section class="metrics" aria-label="Metriky pracoviska"><article class="metric"><span>Všetky zákazky ${icon('file')}</span><strong>${number(s.total)}</strong><small>Aktívne záznamy pracoviska</small></article><article class="metric"><span>Na posúdenie ${icon('clock')}</span><strong>${number(s.pending_review)}</strong><small>Čakajú na rozhodnutie DTP</small></article><article class="metric"><span>Zistené chyby ${icon('warn')}</span><strong>${number(s.by_status.blocked || 0)}</strong><small>Vyžadujú opravený podklad</small></article><article class="metric"><span>Prevzaté operátorom ${icon('check')}</span><strong>${number(s.accepted)}</strong><small>Nie automaticky uvoľnené do tlače</small></article></section><div class="overview-columns"><section class="panel recent-panel"><div class="panel-heading"><div><h2>Posledné zákazky</h2><p>Skutočné výsledky posledných kontrol.</p></div><a class="text-link" href="#jobs">Všetky ${icon('arrow')}</a></div>${jobTable(jobs)}</section><aside class="panel activity-panel"><div class="panel-heading"><div><h2>Aktivita pracoviska</h2><p>Posledných 7 dní · UTC</p></div></div><div class="activity-total"><strong>${number(s.daily.reduce((a,b) => a+b.count,0))}</strong><span>nahraných podkladov</span></div><div class="bar-chart" role="img" aria-label="Denný počet zákaziek: ${s.daily.map(d => `${d.date}: ${d.count}`).join(', ')}">${s.daily.map(d => `<div class="bar-col"><span>${d.count}</span><div class="bar-track"><div class="bar h${Math.round(d.count/max*10)}"></div></div><small>${new Date(`${d.date}T12:00:00Z`).toLocaleDateString('sk',{weekday:'short'})}</small></div>`).join('')}</div><div class="usage-box"><span>Mesačný limit</span><strong>${s.usage.uploads} <small>/ ${s.usage.monthly_limit} súborov</small></strong><progress max="${s.usage.monthly_limit}" value="${s.usage.uploads}" aria-label="Využitie mesačnej kvóty"></progress><p>Úložisko ${bytes(s.usage.storage_bytes)} / ${bytes(s.usage.storage_limit_bytes)}</p></div></aside></div><div class="scope-strip">${icon('shield')}<p><strong>Transparentný rozsah kontroly.</strong> PDF/X, vizuálna spadávka a správnosť farieb vyžadujú profesionálny preflight. Aj podklad bez nálezov čaká na človeka.</p><span>BASIC INSPECT</span></div>`;
}
function jobsView(data: Page<Job>): string {
  return `${heading('DTP FRONT', 'Zákazky', 'Prehľad prijatých podkladov, nálezov a rozhodnutí.', uploadButton())}<section class="panel"><form id="filter-form" class="filter-bar"><label class="search-field">${icon('search')}<span class="sr-only">Hľadať zákazky</span><input name="query" value="${esc(query)}" maxlength="100" placeholder="Názov súboru alebo referencia…"></label><label><span class="sr-only">Filter stavu</span><select name="status"><option value="">Všetky stavy</option>${Object.entries(labels).map(([v,t]) => `<option value="${v}" ${v===statusFilter?'selected':''}>${t}</option>`).join('')}</select></label><button class="btn secondary" type="submit">Filtrovať</button><button class="icon-btn" type="button" data-action="refresh" aria-label="Obnoviť zoznam">↻</button></form>${jobTable(data.items)}<div class="pagination"><span>${data.total ? `${data.offset+1}–${Math.min(data.offset+data.limit,data.total)} z ${data.total}` : '0 zákaziek'}</span><div><button class="btn small secondary" data-action="prev" ${offset===0?'disabled':''}>Predchádzajúce</button><button class="btn small secondary" data-action="next" ${offset+data.limit>=data.total?'disabled':''}>Ďalšie</button></div></div></section>`;
}
function profilesView(): string {
  return `${heading('VERZOVANÉ PRAVIDLÁ', 'Výrobné profily', 'Každá zákazka si uchová presné pravidlá použité pri kontrole.', owner()?'<button class="btn primary" data-action="new-profile">'+icon('plus')+' Vytvoriť profil</button>':'')}<div class="notice">${icon('shield')}<p>Profily definujú vašu výrobnú politiku, nie univerzálny tlačový štandard. Úprava vytvorí novú verziu; staré zákazky zostanú reprodukovateľné.</p></div><section class="profile-grid">${latestProfiles().map(p=>`<article class="panel profile-card"><div class="profile-top"><span class="profile-glyph">${icon('sliders')}</span><span class="version">v${p.version}</span></div><h2>${esc(p.name)}</h2><p class="muted">${p.rules.trim_width_mm ? `${p.rules.trim_width_mm} × ${p.rules.trim_height_mm} mm` : 'Ľubovoľný podporovaný rozmer'}</p><dl><div><dt>Spadávka podľa boxov</dt><dd>${p.rules.bleed_mm} mm</dd></div><div><dt>Minimálne DPI</dt><dd>${p.rules.min_dpi}</dd></div><div><dt>Počet strán</dt><dd>${p.rules.min_pages}–${p.rules.max_pages}</dd></div><div><dt>Vložené fonty</dt><dd>${p.rules.require_embedded_fonts?'Vyžadované':'Nepovinné'}</dd></div><div><dt>RGB na posúdenie</dt><dd>${p.rules.flag_rgb?'Áno':'Nie'}</dd></div></dl><div class="profile-bottom"><code title="${p.digest}">${p.digest.slice(0,12)}…</code>${owner()?`<button class="btn small secondary" data-action="edit-profile" data-id="${p.id}">Nová verzia ${icon('arrow')}</button>`:''}</div></article>`).join('')}</section><details class="panel details-panel"><summary>Všetky uložené verzie (${profiles.length})</summary><div class="table-wrap"><table><thead><tr><th>Profil</th><th>Verzia</th><th>Vytvorené</th><th>Digest pravidiel</th></tr></thead><tbody>${profiles.map(p=>`<tr><td>${esc(p.name)}</td><td>v${p.version}</td><td>${time(p.created_at)}</td><td><code>${p.digest.slice(0,20)}…</code></td></tr>`).join('')}</tbody></table></div></details>`;
}
const actionLabels: Record<string,string> = {'job.uploaded':'Podklad nahraný','job.demo_uploaded':'Syntetický podklad nahraný','job.started':'Kontrola spustená','job.completed':'Kontrola dokončená','job.reviewed':'Rozhodnutie operátora','job.retried':'Kontrola zopakovaná','job.deleted':'Zákazka odstránená','job.files_purged':'Súbory vymazané','profile.created':'Profil vytvorený','auth.login':'Prihlásenie','workspace.created':'Pracovisko vytvorené','job.assistant_generated':'Návrh správy vytvorený','member.created':'Člen pridaný','key.created':'API kľúč vytvorený'};
function auditTable(events: Audit[]): string {
  return events.length ? `<div class="audit-list">${events.map(e=>`<article class="audit-item"><span class="audit-dot"></span><div><strong>${esc(actionLabels[e.action]||e.action)}</strong><p>${e.job_id?`<a href="#job/${e.job_id}">Zákazka ${e.job_id.slice(0,8)}</a>`:'Pracovisko'} · ${e.actor_id ? 'Používateľ '+e.actor_id.slice(0,8) : 'Systém'}</p><details><summary>Technické detaily</summary><pre>${esc(JSON.stringify(e.details,null,2))}</pre></details></div><time>${time(e.created_at)}</time></article>`).join('')}</div>` : empty('Žiadne udalosti','Udalosti sa zaznamenávajú pri práci so systémom.');
}
function jobBaseView(j: Job, events: Audit[]): string {
  const findings = j.report?.findings || [];
  return `<a class="text-link back-link" href="#jobs">${icon('back')} Späť na zákazky</a>${heading(j.order_ref || 'BEZ REFERENCIE', j.filename, `${j.profile_name} · verzia ${j.profile_version} · ${bytes(j.size_bytes)}`, `<div class="heading-actions">${badge(j)}<a class="btn secondary" href="/api/jobs/${j.id}/original">${icon('download')} Originál</a></div>`)}<div class="job-layout"><section class="job-main"><div class="panel preview-panel"><div class="panel-heading"><div><h2>Náhľad prvej strany</h2><p>Rasterizovaný náhľad, nie farebný nátlačok.</p></div><span class="version">${j.summary?.pages || '—'} strán</span></div><div class="preview-canvas">${j.preview_available?`<img src="/api/jobs/${j.id}/preview" alt="Rasterizovaný náhľad prvej strany PDF" class="pdf-preview">`:`<div class="preview-placeholder">${icon(j.status==='processing'?'clock':'file')}<p>${['queued','processing'].includes(j.status)?'Kontrola prebieha. Výsledok sa obnoví automaticky.':'Náhľad nie je dostupný.'}</p></div>`}</div></div><section class="panel findings-panel"><div class="panel-heading"><div><h2>Technické nálezy</h2><p>${j.summary?`${j.summary.errors} chýb · ${j.summary.warnings} upozornení · ${j.summary.info} informácií`:'Čakáme na dokončený report.'}</p></div>${j.report?`<a class="btn small secondary" href="/api/jobs/${j.id}/report">${icon('download')} JSON report</a>`:''}</div>${findings.length?findings.map(f=>`<article class="finding ${f.severity}"><span class="finding-icon">${icon(f.severity==='error'?'warn':f.severity==='warning'?'clock':'file')}</span><div><div class="finding-meta"><code>${esc(f.code)}</code><span>${f.page?'Strana '+f.page:'Dokument'}</span></div><p>${esc(f.message)}</p>${Object.keys(f.evidence).length?`<details><summary>Dôkaz / namerané hodnoty</summary><pre>${esc(JSON.stringify(f.evidence,null,2))}</pre></details>`:''}</div></article>`).join(''):j.status==='review'?'<div class="clean-result">'+icon('check')+'<div><strong>V podporovanom rozsahu bez nálezov.</strong><p>Nie je to potvrdenie pripravenosti na tlač. Pokračujte odborným posúdením.</p></div></div>':empty(j.error_code||'Report ešte nie je pripravený', j.status==='error'?'Zlyhanie spracovania sa nikdy nepovažuje za úspešnú kontrolu.':'Systém čaká na výsledok skenera.')}</section>${j.report?.pages?.length?`<details class="panel details-panel"><summary>Geometria strán (${j.report.pages.length})</summary><div class="table-wrap"><table><thead><tr><th>Strana</th><th>Čistý formát</th><th>Spadávka Ľ / D / P / H</th><th>TrimBox</th></tr></thead><tbody>${j.report.pages.map(p=>`<tr><td>${p.page}</td><td>${p.width_mm} × ${p.height_mm} mm</td><td>${p.bleed_margins_mm.join(' / ')} mm</td><td>${p.explicit_trim_box?'Explicitný':'Odvodený'}</td></tr>`).join('')}</tbody></table></div></details>`:''}${j.report?.images?.length?`<details class="panel details-panel"><summary>Umiestnenia obrázkov (${j.report.images.length})</summary><div class="table-wrap"><table><thead><tr><th>Strana</th><th>Pixely</th><th>Efektívne DPI</th><th>Farby</th></tr></thead><tbody>${j.report.images.map(p=>`<tr><td>${p.page}</td><td>${p.width_px} × ${p.height_px}</td><td>${p.effective_dpi}</td><td>${esc(p.color_space)}</td></tr>`).join('')}</tbody></table></div></details>`:''}${j.report?.fonts?.length?`<details class="panel details-panel"><summary>Použité fonty (${j.report.fonts.length})</summary><div class="table-wrap"><table><thead><tr><th>Strana</th><th>Font</th><th>Typ</th><th>Fontový program</th></tr></thead><tbody>${j.report.fonts.map(p=>`<tr><td>${p.page}</td><td>${esc(p.name)}</td><td>${esc(p.subtype)}</td><td>${p.embedded_program_present?'Prítomný':'Chýba'}</td></tr>`).join('')}</tbody></table></div></details>`:''}<details class="panel details-panel"><summary>Audit zákazky</summary>${auditTable(events)}</details></section><aside class="job-aside"><section class="panel decision-panel"><div class="panel-heading"><div><span class="eyebrow">ĎALŠÍ KROK</span><h2>DTP rozhodnutie</h2></div>${icon('users')}</div><div class="panel-body"><p class="decision-notice">${j.status==='blocked'?'Podklad obsahuje chyby. Vyžiadajte opravenú verziu.':j.status==='review'?'Základná kontrola skončila. Odborník musí overiť nepokryté parametre.':'Rozhodnutie je dostupné až po dokončení kontroly.'}</p>${j.decision?`<div class="review-record">${badge(j)}<p>${esc(j.decision_note)}</p><small>${time(j.reviewed_at)} · ${esc(j.reviewer_id?.slice(0,8))}</small></div>`:canWrite() && ['review','blocked'].includes(j.status)?`<form id="review-form"><label>Poznámka operátora<textarea name="note" required minlength="10" maxlength="2000" rows="3" placeholder="Čo ste overili a aký bude ďalší postup?"></textarea></label><label class="checkbox"><input type="checkbox" name="acknowledge" required><span>Rozumiem, že ide o interné posúdenie. Nie o automatické schválenie do tlače.</span></label><p class="form-error" role="alert"></p><div class="review-buttons">${j.status==='review'?'<button class="btn primary full" name="decision" value="accepted">'+icon('check')+' Prevziať na DTP</button>':''}<button class="btn secondary full" name="decision" value="rejected">Vrátiť podklad na opravu</button></div></form>`:''}${canWrite() && j.status==='error'?`<button class="btn secondary full" data-action="retry" ${j.attempts>=3?'disabled':''}>Zopakovať kontrolu (${j.attempts}/3)</button>`:''}</div></section>${canWrite() && ['review','blocked'].includes(j.status)?`<section class="panel assistant-panel"><div class="panel-heading"><div><h2>${icon('spark')} DTP asistent</h2><p>${me?.capabilities.assistant_mode==='ollama'?'Ollama · voliteľný lokálny model':'Pravidlová šablóna · bez LLM'}</p></div></div><div class="panel-body"><p>Pripraví návrh správy z konkrétnych nálezov. Nič neposiela zákazníkovi ani nemení v PDF.</p><button class="btn secondary full" data-action="assistant">Vytvoriť návrh správy ${icon('arrow')}</button><div id="assistant-output" aria-live="polite"></div></div></section>`:''}<section class="panel identity-panel"><div class="panel-heading"><h2>Identita kontroly</h2></div><div class="panel-body"><label>SHA-256 originálu<code class="hash">${esc(j.sha256)}</code></label><label>Digest profilu<code class="hash">${esc(j.profile_digest||'—')}</code></label><label>Digest reportu<code class="hash">${esc(j.report_digest||'Čaká na spracovanie')}</code></label><p class="muted">Engine: ${esc(j.report?.engine?.name||'—')} ${esc(j.report?.engine?.version||'')}</p></div></section><details class="panel details-panel"><summary>Rozsah a obmedzenia</summary><div class="panel-body"><p><strong>print_ready = false<br>release_allowed = false</strong></p>${Object.entries(j.report?.coverage||{}).map(([k,v])=>`<div class="coverage"><code>${esc(k)}</code><p>${esc(v)}</p></div>`).join('')}</div></details>${owner()?`<button class="btn text-danger full" data-action="delete-job" ${j.status==='processing'?'disabled':''}>Vymazať zákazku a súbory</button>`:''}</aside></div>`;
}
function jobView(j: Job, events: Audit[]): string {
  const html = jobBaseView(j, events);
  const metadata = j.report?.metadata || {};
  if (!Object.keys(metadata).length) return html;
  const panel = `<details class="panel details-panel"><summary>PDF metadata</summary><div class="panel-body metadata-list">${Object.entries(metadata).map(([key,value])=>`<div><dt>${esc(key)}</dt><dd>${esc(value)}</dd></div>`).join('')}</div></details>`;
  return html.replace('</section><aside class="job-aside">', `${panel}</section><aside class="job-aside">`);
}
function settingsView(members: User[], keys: Key[]): string {
  if (!me) return '';
  return `${heading('SPRÁVA PRACOVISKA','Nastavenia','Prístupy, integrácie a využitie pilotnej služby.')}<div class="settings-grid"><section class="panel"><div class="panel-heading"><h2>Pracovisko</h2></div><div class="panel-body"><label>Názov<strong>${esc(me.workspace.name)}</strong></label><label>ID pracoviska<code class="hash">${me.workspace.id}</code></label><dl class="settings-facts"><div><dt>Režim</dt><dd>${esc(me.workspace.plan)} / bez fakturácie</dd></div><div><dt>Retencia súborov</dt><dd>${me.workspace.retention_days} dní</dd></div><div><dt>Limit jedného PDF</dt><dd>${me.capabilities.max_upload_mb} MB</dd></div><div><dt>Lokálny asistent</dt><dd>${esc(me.capabilities.assistant_mode)}</dd></div><div><dt>Automatické úpravy / print release</dt><dd>Vypnuté</dd></div></dl><p class="muted">Limity nastavuje správca prevádzky. Táto verzia nepripája platobnú bránu.</p></div></section><section class="panel"><div class="panel-heading"><h2>Zmena hesla</h2></div><div class="panel-body"><form id="password-form"><label>Aktuálne heslo<input name="old_password" type="password" autocomplete="current-password" required></label><label>Nové heslo<input name="new_password" type="password" autocomplete="new-password" required minlength="12" maxlength="256" placeholder="Aspoň 12 znakov"></label><p class="form-error" role="alert"></p><button class="btn secondary" type="submit">Zmeniť heslo a odhlásiť relácie</button></form></div></section></div>${owner()?`<section class="panel section-gap"><div class="panel-heading"><div><h2>Členovia tímu</h2><p>Vlastník spravuje, operátor kontroluje, pozorovateľ iba číta.</p></div><button class="btn secondary" data-action="member">${icon('plus')} Pridať člena</button></div><div class="table-wrap"><table><thead><tr><th>E-mail</th><th>Rola</th><th>Stav</th><th>Prístup</th></tr></thead><tbody>${members.map(u=>`<tr><td>${esc(u.email)}</td><td>${roleLabel(u.role)}</td><td>${u.active?'Aktívny':'Deaktivovaný'}</td><td>${u.id!==me?.user.id&&u.active?`<button class="btn small text-danger" data-action="deactivate-member" data-id="${u.id}">Deaktivovať</button>`:'—'}</td></tr>`).join('')}</tbody></table></div></section><section class="panel section-gap"><div class="panel-heading"><div><h2>Integračné API kľúče</h2><p>Token sa ukáže iba raz. Platnosť najviac 90 dní. Žiadne právo schvaľovať.</p></div><button class="btn secondary" data-action="key">${icon('plus')} Nový kľúč</button></div>${keys.length?`<div class="table-wrap"><table><thead><tr><th>Názov</th><th>Prefix</th><th>Rozsah</th><th>Exspirácia</th><th>Stav</th></tr></thead><tbody>${keys.map(k=>`<tr><td>${esc(k.name)}</td><td><code>${esc(k.prefix)}…</code></td><td>${esc(k.scope)}</td><td>${time(k.expires_at)}</td><td>${k.revoked_at?'Zrušený':k.expires_at*1000<Date.now()?'Expirovaný':`<button class="btn small text-danger" data-action="revoke-key" data-id="${k.id}">Zrušiť</button>`}</td></tr>`).join('')}</tbody></table></div>`:empty('Zatiaľ bez API kľúčov','Vytvorte kľúč pre automatické nahrávanie z vášho systému alebo priečinka.')}<div class="panel-body"><p class="muted">Autentifikovaná schéma API: <a href="/api/openapi.json" target="_blank" rel="noopener">/api/openapi.json</a></p></div></section>`:''}`;
}
async function load(): Promise<void> {
  if (!me) {renderLogin(); return;}
  const seq = ++generation;
  const view = route();
  try {
    const [newStats, newProfiles] = await Promise.all([api<Stats>('/api/stats'),api<Profile[]>('/api/profiles')]);
    if (seq !== generation || !me) return;
    stats = newStats; profiles = newProfiles;
    let content: string;
    if (view.startsWith('job/')) {
      const id = encodeURIComponent(view.slice(4));
      const [job, events] = await Promise.all([api<Job>(`/api/jobs/${id}`),api<Page<Audit>>(`/api/audit?job_id=${id}&limit=50`)]);
      currentJob = job; content = jobView(job,events.items);
    } else if (view==='jobs') {
      const params = new URLSearchParams({q:query,status:statusFilter,offset:String(offset),limit:'20'});
      content = jobsView(await api<Page<Job>>(`/api/jobs?${params}`));
    } else if (view==='profiles') content = profilesView();
    else if (view==='audit') {
      const events = await api<Page<Audit>>(`/api/audit?limit=50&offset=${offset}`);
      content = `${heading('DOHĽADATEĽNOSŤ','Auditná stopa','Prevádzkový audit. Nie kryptograficky nemenný WORM archív.')}<section class="panel">${auditTable(events.items)}<div class="pagination"><span>${events.total} udalostí</span><div><button class="btn small secondary" data-action="audit-prev" ${offset===0?'disabled':''}>Predchádzajúce</button><button class="btn small secondary" data-action="audit-next" ${offset+50>=events.total?'disabled':''}>Ďalšie</button></div></div></section>`;
    } else if (view==='settings') {
      const [members, keys] = owner()?await Promise.all([api<User[]>('/api/members'),api<Key[]>('/api/keys')]):[[],[]];
      content = settingsView(members, keys);
    } else {const jobs = await api<Page<Job>>('/api/jobs?limit=6'); content = overview(newStats,jobs.items);}
    if (seq !== generation || !me) return;
    shell(content,view);
  } catch (error) {
    if (seq!==generation) return;
    if (error instanceof ApiError && error.status===401) {fail(error); return;}
    shell(`${heading('PRIPOJENIE','Údaje sa nepodarilo načítať',errorMessage(error))}<button class="btn primary" data-action="refresh">Skúsiť znova</button>`, view);
  }
}
function openModal(title: string, subtitle: string, body: string): void {
  previousFocus = document.activeElement as HTMLElement | null;
  modal.innerHTML = `<div class="modal-heading"><div><span class="eyebrow">PRESSPILOT</span><h2 id="modal-title">${esc(title)}</h2><p>${esc(subtitle)}</p></div><button class="icon-btn" data-action="close-modal" aria-label="Zavrieť">${icon('x')}</button></div>${body}`;
  if (!modal.open) modal.showModal();
}
modal.addEventListener('close',()=>{modal.innerHTML=''; previousFocus?.focus();});
modal.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
function uploadModal(): void {
  uploadFile=null; uploadKey=crypto.randomUUID(); uploadMetadata='';
  openModal('Nová kontrola PDF','Originál bezpečne uložíme a zaradíme do fronty.',`<form id="upload-form"><label class="dropzone" id="dropzone">${icon('upload')}<strong>Vyberte alebo pretiahnite PDF</strong><span id="file-label">Jeden dokument · najviac ${me?.capabilities.max_upload_mb} MB · do 200 strán</span><input type="file" name="file" accept="application/pdf,.pdf" id="file-input" class="file-input"></label><label>Výrobný profil<select name="profile_id" required>${latestProfiles().map(p=>`<option value="${p.id}">${esc(p.name)} · v${p.version}</option>`).join('')}</select></label><label>Referencia zákazky <span class="optional">voliteľné</span><input name="order_ref" maxlength="100" placeholder="Napríklad OBJ-2026-0142"></label><div class="notice compact">${icon('shield')}<p>Žiadne automatické opravy ani potvrdenie „print-ready“. Výsledok vždy prejde do DTP posúdenia.</p></div><p class="form-error" role="alert"></p><button class="btn primary full" type="submit">${icon('upload')} Nahrať a skontrolovať</button></form>`);
}
function chooseFile(file?: File): void {
  if (!file) return;
  const error = !file.name.toLowerCase().endsWith('.pdf')?'Vyberte PDF dokument.':file.size>(me?.capabilities.max_upload_mb||25)*1024**2?'Súbor je príliš veľký.':null;
  if(error){toast(error,true);return;}
  uploadFile=file;uploadKey=crypto.randomUUID();uploadMetadata='';
  document.getElementById('file-label')!.textContent=`${file.name} · ${bytes(file.size)}`;
  document.getElementById('dropzone')?.classList.add('selected');
}
function profileModal(profile?: Profile): void {
  editingProfile=profile;
  const r: Rules=profile?.rules||{trim_width_mm:null,trim_height_mm:null,tolerance_mm:0.5,bleed_mm:3,min_dpi:300,min_pages:1,max_pages:200,require_embedded_fonts:true,require_explicit_trim:false,flag_rgb:false};
  const numeric=(name:string,label:string,v:number|null,min:number,max:number,step='1')=>`<label>${label}<input name="${name}" type="number" min="${min}" max="${max}" step="${step}" value="${v??''}" ${name.startsWith('trim_')?'':'required'}></label>`;
  openModal(profile?'Nová verzia profilu':'Nový výrobný profil','Existujúce zákazky zostanú naviazané na pôvodnú verziu.',`<form id="profile-form"><label>Názov profilu<input name="name" required minlength="2" maxlength="120" value="${esc(profile?.name||'')}"></label><div class="form-grid">${numeric('trim_width_mm','Čistá šírka (mm) · voliteľné',r.trim_width_mm,10,3000,'0.01')}${numeric('trim_height_mm','Čistá výška (mm) · voliteľné',r.trim_height_mm,10,3000,'0.01')}${numeric('bleed_mm','Spadávka (mm)',r.bleed_mm,0,20,'0.1')}${numeric('tolerance_mm','Tolerancia rozmeru (mm)',r.tolerance_mm,0.05,3,'0.05')}${numeric('min_dpi','Minimálne efektívne DPI',r.min_dpi,36,2400)}${numeric('min_pages','Minimálny počet strán',r.min_pages,1,200)}${numeric('max_pages','Maximálny počet strán',r.max_pages,1,200)}</div>${[['require_embedded_fonts','Vyžadovať vložený fontový program'],['require_explicit_trim','Vyžadovať explicitný TrimBox'],['flag_rgb','RGB označiť na odborné posúdenie']].map(([key,text])=>`<label class="checkbox"><input name="${key}" type="checkbox" ${r[key as keyof Rules]?'checked':''}><span>${text}</span></label>`).join('')}<p class="form-error" role="alert"></p><button class="btn primary full">Uložiť ${profile?'novú verziu':'profil'}</button></form>`);
}
function memberModal(): void {openModal('Pridať člena tímu','Heslo odovzdajte bezpečným kanálom. Používateľ si ho môže zmeniť.',`<form id="member-form"><label>E-mail<input name="email" type="email" required></label><label>Dočasné heslo<input name="password" type="password" required minlength="12" maxlength="256" autocomplete="new-password"></label><label>Rola<select name="role"><option value="operator">DTP operátor</option><option value="viewer">Pozorovateľ</option><option value="owner">Vlastník</option></select></label><p class="form-error" role="alert"></p><button class="btn primary full">Vytvoriť prístup</button></form>`);}
function keyModal(): void {openModal('Vytvoriť API kľúč','Kľúče nemajú právo rozhodovať o zákazke ani spravovať pracovisko.',`<form id="key-form"><label>Názov integrácie<input name="name" required minlength="2" maxlength="80" placeholder="Napríklad Hot folder"></label><label>Rozsah<select name="scope"><option value="upload">Čítanie a nahrávanie PDF</option><option value="read">Iba čítanie</option></select></label><label>Platnosť v dňoch<input name="expires_days" type="number" min="1" max="90" value="30" required></label><p class="form-error" role="alert"></p><button class="btn primary full">Vygenerovať kľúč</button></form>`);}
async function handleForm(form: HTMLFormElement, event: SubmitEvent): Promise<void> {
  if(busy)return;
  const data = new FormData(form);
  const str = (name:string):string=>String(data.get(name)||'');
  const buttons = Array.from(form.querySelectorAll<HTMLButtonElement>('button[type="submit"], button:not([type])'));
  const err = form.querySelector<HTMLElement>('.form-error');
  if(err)err.textContent='';
  busy=true;buttons.forEach(b=>b.disabled=true);form.setAttribute('aria-busy','true');
  try {
    switch(form.id){
      case 'login-form': {
        const result=await api<{csrf_token:string}>('/api/auth/login','POST',{workspace_id:str('workspace_id').trim(),email:str('email'),password:str('password')});
        setCsrf(result.csrf_token);me=await api<Me>('/api/me');
        try{localStorage.setItem('pp_workspace_id',me.workspace.id);}catch{}
        location.hash='home';await load();break;
      }
      case 'filter-form':query=str('query');statusFilter=str('status');offset=0;await load();break;
      case 'upload-form':{
        if(!uploadFile)throw new Error('Najprv vyberte PDF súbor.');
        const metadata=JSON.stringify([str('profile_id'),str('order_ref')]);
        if(uploadMetadata&&uploadMetadata!==metadata)uploadKey=crypto.randomUUID();
        uploadMetadata=metadata;
        const payload=new FormData();payload.set('file',uploadFile);payload.set('profile_id',str('profile_id'));payload.set('order_ref',str('order_ref'));
        const job=await api<Job>('/api/jobs','POST',payload,{'Idempotency-Key':uploadKey});
        modal.close();location.hash=`job/${job.id}`;toast('PDF uložené. Kontrola je zaradená do fronty.');await load();break;
      }
      case 'profile-form':{
        const rules:Rules={trim_width_mm:str('trim_width_mm')?Number(str('trim_width_mm')):null,trim_height_mm:str('trim_height_mm')?Number(str('trim_height_mm')):null,tolerance_mm:Number(str('tolerance_mm')),bleed_mm:Number(str('bleed_mm')),min_dpi:Number(str('min_dpi')),min_pages:Number(str('min_pages')),max_pages:Number(str('max_pages')),require_embedded_fonts:data.has('require_embedded_fonts'),require_explicit_trim:data.has('require_explicit_trim'),flag_rgb:data.has('flag_rgb')};
        await api('/api/profiles','POST',{name:str('name'),rules,base_profile_id:editingProfile?.id||null});modal.close();toast('Nová verzia profilu je uložená.');await load();break;
      }
      case 'review-form':{
        const decision=(event.submitter as HTMLButtonElement|null)?.value;
        if(!currentJob||!decision)throw new Error('Vyberte rozhodnutie.');
        await api(`/api/jobs/${currentJob.id}/review`,'POST',{decision,note:str('note'),acknowledge_limits:data.has('acknowledge')});toast('Rozhodnutie je uložené v audite.');await load();break;
      }
      case 'password-form':await api('/api/auth/password','POST',{old_password:str('old_password'),new_password:str('new_password')});me=null;setCsrf('');renderLogin();toast('Heslo zmenené. Prihláste sa znova.');break;
      case 'member-form':await api('/api/members','POST',{email:str('email'),password:str('password'),role:str('role')});modal.close();toast('Člen bol vytvorený.');await load();break;
      case 'key-form':{
        const result=await api<{token:string;expires_at:number}>('/api/keys','POST',{name:str('name'),scope:str('scope'),expires_days:Number(str('expires_days'))});
        openModal('API kľúč je vytvorený','Skopírujte ho teraz. Neskôr sa už nezobrazí.',`<label>Tajný token<textarea id="key-value" readonly rows="3" spellcheck="false">${esc(result.token)}</textarea></label><button class="btn primary full" data-action="copy-key">Skopírovať kľúč</button><p class="muted">Platný do ${time(result.expires_at)}. Nevkladajte ho do prehliadačového kódu ani do Gitu.</p>`);await load();break;
      }
    }
  }catch(error){if(err && err.isConnected)err.textContent=errorMessage(error);else fail(error);}
  finally{busy=false;buttons.forEach(b=>b.disabled=false);form.removeAttribute('aria-busy');}
}
document.addEventListener('submit',e=>{const form=e.target;if(form instanceof HTMLFormElement){e.preventDefault();void handleForm(form,e as SubmitEvent);}});
document.addEventListener('change',e=>{if(e.target instanceof HTMLInputElement&&e.target.id==='file-input')chooseFile(e.target.files?.[0]);});
document.addEventListener('dragover',e=>{const target=e.target as HTMLElement;if(target.closest('#dropzone')){e.preventDefault();document.getElementById('dropzone')?.classList.add('dragover');}});
document.addEventListener('dragleave',e=>{if((e.target as HTMLElement).closest('#dropzone'))document.getElementById('dropzone')?.classList.remove('dragover');});
document.addEventListener('drop',e=>{if((e.target as HTMLElement).closest('#dropzone')){e.preventDefault();document.getElementById('dropzone')?.classList.remove('dragover');chooseFile(e.dataTransfer?.files[0]);}});
document.addEventListener('click',e=>{
  const target=e.target as HTMLElement;
  const button=target.closest<HTMLElement>('[data-action]');
  if(!button)return;
  const action=button.dataset.action;
  void (async()=>{
    if(button instanceof HTMLButtonElement && button.disabled)return;
    try {
      switch(action){
        case 'menu':document.querySelector('.sidebar')?.classList.toggle('visible');break;
        case 'close-modal':if(!busy)modal.close();break;
        case 'upload':uploadModal();break;
        case 'new-profile':profileModal();break;
        case 'edit-profile':profileModal(profiles.find(p=>p.id===button.dataset.id));break;
        case 'member':memberModal();break;
        case 'key':keyModal();break;
        case 'refresh':await load();break;
        case 'prev':offset=Math.max(0,offset-20);await load();break;
        case 'next':offset+=20;await load();break;
        case 'audit-prev':offset=Math.max(0,offset-50);await load();break;
        case 'audit-next':offset+=50;await load();break;
        case 'logout':await api('/api/auth/logout','POST');me=null;setCsrf('');generation++;renderLogin();break;
        case 'retry':if(currentJob){await api(`/api/jobs/${currentJob.id}/retry`,'POST');toast('Kontrola bola znovu zaradená do fronty.');await load();}break;
        case 'delete-job':if(currentJob && confirm('Vymazať túto zákazku a originálny súbor? Prevádzkový audit zostane zachovaný.')){await api(`/api/jobs/${currentJob.id}`,'DELETE');location.hash='jobs';toast('Zákazka a súbory boli vymazané.');}break;
        case 'deactivate-member':if(confirm('Deaktivovať člena a zrušiť jeho relácie aj API kľúče?')){await api(`/api/members/${button.dataset.id}`,'DELETE');await load();}break;
        case 'revoke-key':if(confirm('Natrvalo zrušiť tento integračný kľúč?')){await api(`/api/keys/${button.dataset.id}`,'DELETE');await load();}break;
        case 'copy-key':{const input=document.getElementById('key-value') as HTMLTextAreaElement;try{await navigator.clipboard.writeText(input.value);toast('Kľúč skopírovaný.');}catch{input.focus();input.select();toast('Kľúč je označený. Skopírujte ho systémovým príkazom.');}break;}
        case 'assistant':{
          if(!currentJob)return;
          const output=document.getElementById('assistant-output');if(!output)return;
          (button as HTMLButtonElement).disabled=true;output.textContent='Pripravujem návrh…';
          try{const result=await api<Assistant>(`/api/jobs/${currentJob.id}/assistant`,'POST');output.innerHTML=`<label class="section-gap">Návrh na kontrolu človekom<textarea rows="9" readonly>${esc(result.text)}</textarea></label><small>${esc(result.mode)} · ${result.warning?esc(result.warning):'Správa nebola nikam odoslaná.'}</small>`;}
          finally{(button as HTMLButtonElement).disabled=false;}
          break;
        }
      }
    }catch(error){fail(error);}
  })();
});
window.addEventListener('hashchange',()=>{offset=0;void load();});
setInterval(()=>{
  if(!me||busy||modal.open||document.hidden)return;
  const focused=document.activeElement;
  if(focused instanceof HTMLInputElement||focused instanceof HTMLTextAreaElement||focused instanceof HTMLSelectElement)return;
  const running=!!((stats?.by_status.queued||0)+(stats?.by_status.processing||0));
  if(running && ['home','jobs'].includes(route()) || route().startsWith('job/') && currentJob && ['queued','processing'].includes(currentJob.status))void load();
},4000);
async function boot():Promise<void>{
  try{me=await api<Me>('/api/me');setCsrf(me.csrf_token);await load();}
  catch(error){renderLogin();if(!(error instanceof ApiError&&error.status===401))toast(errorMessage(error),true);}
}
void boot();
