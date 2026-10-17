export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const time = (stamp) => stamp ? new Intl.DateTimeFormat('sk', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(stamp * 1000) : '—';
export const number = (n) => new Intl.NumberFormat('sk').format(n);
export const bytes = (n) => n >= 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(2)} GB` : n >= 1024 ** 2 ? `${(n / 1024 ** 2).toFixed(1)} MB` : `${Math.ceil(n / 1024)} kB`;
export const labels = { queued: 'Vo fronte', processing: 'Kontroluje sa', review: 'Na posúdenie', blocked: 'Zistené chyby', error: 'Chyba kontroly', accepted: 'Prevzaté DTP', rejected: 'Vrátené' };
export function badge(job) {
    const status = job.decision || job.status;
    return `<span class="badge ${esc(status)}"><span class="dot"></span>${labels[status] || esc(status)}</span>`;
}
const paths = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
    sliders: '<path d="M4 6h7m5 0h4M4 12h2m5 0h9M4 18h10m5 0h1"/><circle cx="13.5" cy="6" r="2.5"/><circle cx="8.5" cy="12" r="2.5"/><circle cx="16.5" cy="18" r="2.5"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    settings: '<path d="m9 3-.5 2-2 1-2-.5-2 3 1.5 1.5v3L2.5 15l2 3 2-.5 2 1 .5 2h4l.5-2 2-1 2 .5 2-3-1.5-2v-2L20 9l-2-3-2 .5-2-1L13 3z"/><circle cx="11" cy="12" r="3"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    shield: '<path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7z"/><path d="m8 12 3 3 5-6"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    back: '<path d="M20 12H4m6-6-6 6 6 6"/>',
    x: '<path d="m6 6 12 12M6 18 18 6"/>',
    warn: '<path d="m12 3 10 18H2zM12 9v5m0 3v1"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    spark: '<path d="m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6z"/>',
    logout: '<path d="M9 4H4v16h5m5-13 5 5-5 5m-7-5h12"/>',
    users: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v2"/>',
    download: '<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>'
};
export const icon = (name) => `<svg class="icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.file}</svg>`;
export function toast(message, error = false) {
    const item = document.createElement('div');
    item.className = `toast ${error ? 'danger' : ''}`;
    item.textContent = message;
    document.getElementById('toasts').append(item);
    setTimeout(() => item.remove(), error ? 12_000 : 6_000);
}
export const empty = (title, text) => `<div class="empty">${icon('file')}<h3>${esc(title)}</h3><p>${esc(text)}</p></div>`;
export function jobTable(jobs) {
    if (!jobs.length)
        return empty('Zatiaľ žiadne zákazky', 'Nahrajte PDF alebo zmeňte filter. Zobrazené údaje vždy pochádzajú zo servera.');
    return `<div class="table-wrap"><table><thead><tr><th>Dokument / zákazka</th><th>Výrobný profil</th><th>Výsledok</th><th>Vytvorené</th><th><span class="sr-only">Detail</span></th></tr></thead><tbody>${jobs.map(j => `<tr><td><div class="file-cell"><span class="file-icon">${icon('file')}</span><div><a class="row-link" href="#job/${j.id}">${esc(j.filename)}</a><small>${esc(j.order_ref || 'Bez referencie')} <span>·</span> ${bytes(j.size_bytes)}</small></div></div></td><td><span>${esc(j.profile_name)}</span><small>Verzia ${j.profile_version}</small></td><td>${badge(j)}${j.summary?.errors ? `<small>${j.summary.errors} chýb · ${j.summary.warnings} upozornení</small>` : ''}</td><td class="muted nowrap">${time(j.created_at)}</td><td><a class="icon-btn" href="#job/${j.id}" aria-label="Detail ${esc(j.filename)}">${icon('arrow')}</a></td></tr>`).join('')}</tbody></table></div>`;
}
