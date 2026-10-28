// Registry management for the dashboard: add, find, locate, rename, and remove projects, and
// reveal folders. The server inlines this file only in local mode; share pages never get it.
(function () {
  'use strict';
  const MC = window.MC;
  const { h, icon, both } = MC;

  async function post(path, body) {
    let r;
    try {
      r = await fetch(path, { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    } catch (e) {
      return { ok: false, error: 'The server did not answer' };
    }
    let d = null;
    try { d = await r.json(); } catch (_) {}
    if (!d || typeof d !== 'object') d = { ok: false, error: 'Request failed (' + r.status + ')' };
    return d;
  }
  const project = (name) => (MC.data.projects || []).find((p) => p.name === name);
  function ideaPath(x) {
    const p = project(x.project);
    return p && p.path ? p.path.replace(/\/$/, '') + '/' + x.name : x.name;
  }
  async function reveal(projectName, idea) {
    const d = await post('/api/reveal', { project: projectName, idea: idea || '' });
    if (!d.ok) MC.toast(d.error || 'Could not reveal the folder');
  }
  async function removeProject(name) {
    if (!confirm('Remove "' + name + '" from the list? No files are deleted.')) return;
    const d = await post('/api/roots/remove', { name });
    if (!d.ok) { MC.toast(d.error || 'Could not remove'); return; }
    MC.toast('Removed ' + name);
    await MC.refresh(true);
    MC.go({ project: 'all', page: 'ideas' }, true);
  }
  async function renameProject(name) {
    const next = prompt('New name for ' + name, name);
    if (next == null || !next.trim() || next.trim() === name) return;
    const d = await post('/api/roots/rename', { name, new_name: next.trim() });
    if (!d.ok) { MC.toast(d.error || 'Could not rename'); return; }
    await MC.refresh(true);
    MC.go({ project: d.name }, false);
  }

  // ── Collections: the open menu turns into a list of collections (Back returns) ──
  // target: {key: "project" or "project/idea", name, current: its collection or null, removable}
  function collectionList(menu, target, title, back) {
    const cols = MC.collections;
    const items = [{ icon: 'chevron-left', label: title, cls: 'hd', keep: true, run: back }, { sep: true }];
    for (const c of cols) {
      items.push({ label: c.name, radio: true, check: c.name === target.current, n: c.n, cur: c.name === target.current,
        run: () => { if (c.name !== target.current) setCollection(target, c.name); } });
    }
    if (cols.length) items.push({ sep: true });
    items.push({ icon: 'plus', label: 'New collection', keep: true, cur: !target.current,
      run: () => newCollectionRow(menu, target, title, back, items) });
    if (target.removable) {
      items.push({ icon: 'x', label: target.key.includes('/') ? 'Remove from collection' : 'Remove ' + target.name + ' from collection',
        run: () => setCollection(target, '') });
    }
    MC.swapMenu(menu, items, title, { cols: true, back });
  }
  function newCollectionRow(menu, target, title, back, items) {
    const max = 40;
    const input = h('input', { type: 'text', maxlength: String(max), placeholder: 'Collection name', autocomplete: 'off',
      spellcheck: 'false', 'aria-label': 'New collection name' });
    const msg = h('p', { class: 'in-msg', role: 'alert', hidden: true });
    const row = h('div', { class: 'in' }, icon('plus', 'sm'), input);
    const at = items.findIndex((it) => it.label === 'New collection');
    const next = items.slice(0, at).concat([{ el: row }, { el: msg }], items.slice(at + 1));
    MC.swapMenu(menu, next, title, { cols: true, back, focus: input });
    const cancel = () => collectionList(menu, target, title, back);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cancel(); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        const name = input.value.trim();
        const bad = !name ? 'Type a name' : name.length > max ? 'Use at most ' + max + ' characters' : /[\p{Cc}\p{Cf}]/u.test(name) ? 'Remove the control or invisible characters' : '';
        input.classList.toggle('err', !!bad);
        input.setAttribute('aria-invalid', String(!!bad));
        msg.hidden = !bad;
        msg.textContent = bad;
        if (!bad) setCollection(target, name);
      }
    });
  }
  async function setCollection(target, name) {
    MC.closeMenu();
    const d = await post('/api/roots/collection', { key: target.key, collection: name });
    if (!d.ok) { MC.toast(d.error || 'Could not change the collection'); return; }
    MC.toast(name ? (target.current ? 'Moved ' : 'Added ') + target.name + ' to ' + name : 'Removed ' + target.name + ' from ' + target.current);
    await MC.refresh(true);
  }
  const collections = () => MC.data.mode !== 'single';   // one design folder has no registry to keep them in

  // ── Add project dialog: Folder path and Find in folders ──
  function openAdd(o) {
    o = o || {};
    let tab = o.tab === 'find' ? 'find' : 'path';
    let check = null, seq = 0, timer = 0, busy = false;
    const close = () => MC.closeLayer();

    const pathIn = h('input', { class: 'input mono', id: 'add-path', type: 'text', placeholder: '~/project/design',
      autocomplete: 'off', spellcheck: 'false', 'aria-describedby': 'add-msg' });
    pathIn.value = o.path || '';
    const nameIn = h('input', { class: 'input', id: 'add-name', type: 'text', autocomplete: 'off', spellcheck: 'false' });
    nameIn.value = o.name || '';
    const msg = h('div', { id: 'add-msg', 'aria-live': 'polite' });
    const sug = h('div', { class: 'suggest', hidden: true });
    const cli = h('span', { class: 'mono' });
    const addBtn = h('button', { class: 'btn primary', type: 'button', disabled: true }, 'Add project');
    const cancel = h('button', { class: 'btn ghost', type: 'button', onclick: close }, 'Cancel');

    const scanIn = h('input', { class: 'input mono', id: 'scan-dir', type: 'text', placeholder: '~/work, ~/projects',
      autocomplete: 'off', spellcheck: 'false' });
    scanIn.value = '~';
    const scanList = h('div', { class: 'scanlist' });
    const scanMsg = h('p', { class: 'status-line', 'aria-live': 'polite' });
    const scanBtn = h('button', { class: 'btn', type: 'button' }, icon('search', 'sm'), 'Search');
    const addSel = h('button', { class: 'btn primary', type: 'button', disabled: true }, 'Add selected');

    const pathBody = h('div', { class: 'db' },
      h('div', { class: 'field' }, h('label', { class: 'lab', for: 'add-path' }, 'Design folder'), pathIn, msg),
      sug,
      h('div', { class: 'field' }, h('label', { class: 'lab', for: 'add-name' }, 'Name ', h('span', { class: 't3', text: 'optional' })),
        nameIn, h('span', { class: 'hint' }, h('span', { class: 'ph-hide', text: 'Shown in the side rail and in URLs. ' }), 'Leave empty to use the folder name.')));
    const findBody = h('div', { class: 'db' },
      h('div', { class: 'field' }, h('label', { class: 'lab', for: 'scan-dir' }, 'Folders to search'),
        h('div', { class: 'scanrow' }, scanIn, scanBtn),
        h('span', { class: 'hint', text: 'Separate folders with commas. Searches up to 5 levels for design folders that hold canvas.json.' })),
      scanMsg, scanList);
    const tabs = h('div', { class: 'seg', role: 'tablist', 'aria-label': 'How to add' });
    const tabBtn = (k, ic, label) => {
      const b = h('button', { type: 'button', role: 'tab' }, icon(ic, 'sm'), label);
      b.addEventListener('click', () => { tab = k; paint(); (k === 'path' ? pathIn : scanIn).focus(); });
      tabs.append(b);
      return b;
    };
    const tPath = tabBtn('path', 'folder', 'Folder path');
    const tFind = tabBtn('find', 'folder-search', both('Find in folders', 'Find'));
    const foot = h('div', { class: 'df' }, cli, h('span', { class: 'sp' }), cancel, addBtn, addSel);
    const dlg = h('div', { class: 'dialog dlg', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'dlg-t' },
      h('div', { class: 'grab' }),
      h('div', { class: 'dh' }, h('h2', { id: 'dlg-t', text: 'Add a project' }),
        h('button', { class: 'icon-btn sm', type: 'button', 'aria-label': 'Close', onclick: close }, icon('x'))),
      h('p', { class: 'dsub', text: 'A project is a design folder that holds one or more ideas.' }),
      h('div', { class: 'dt' }, tabs), pathBody, findBody, foot);
    MC.openLayer([h('div', { class: 'scrim', onclick: close }), dlg], () => clearTimeout(timer));
    dlg.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); } });

    function lastSeg(p) { const s = p.replace(/\/+$/, '').split('/'); return s[s.length - 1] || ''; }
    function paint() {
      const onPath = tab === 'path';
      tPath.classList.toggle('on', onPath); tPath.setAttribute('aria-selected', String(onPath));
      tFind.classList.toggle('on', !onPath); tFind.setAttribute('aria-selected', String(!onPath));
      pathBody.hidden = !onPath; findBody.hidden = onPath;
      addBtn.hidden = !onPath; addSel.hidden = onPath;
      cli.hidden = !onPath;
      const p = pathIn.value.trim(), n = nameIn.value.trim();
      cli.textContent = 'canvas roots add ' + (p ? MC.shq(p) : '<design dir>') + (n ? ' --name ' + MC.shq(n) : '');
      msg.textContent = '';
      pathIn.classList.remove('err');
      sug.hidden = true;
      sug.textContent = '';
      addBtn.disabled = busy || !(check && check.ok && check.path === p);
      if (check && check.path === p && p) {
        if (check.ok) {
          msg.append(h('p', { class: 'okmsg' }, icon('check', 'sm'),
            'Found ' + MC.plural(check.ideas, 'idea') + ', ' + MC.plural(check.boards, 'board') + (check.replaces ? '. Updates the missing folder of ' + check.name : '')));
        } else {
          pathIn.classList.add('err');
          msg.append(h('p', { class: 'errmsg', role: 'alert' }, icon('alert', 'sm'), h('span', { text: check.error })));
          if (check.suggest) {
            const s = check.suggest;
            sug.hidden = false;
            sug.append(h('div', { class: 'sg-h' }, icon('folder-search', 'sm'), 'Found a design folder inside it'),
              h('div', { class: 'sg-r' }, h('span', { class: 'mono', text: s.path }),
                h('span', { class: 't3', text: MC.plural(s.ideas, 'idea') + ', ' + MC.plural(s.boards, 'board') }),
                h('button', { class: 'btn sm', type: 'button', onclick: () => { pathIn.value = s.path; changed(true); pathIn.focus(); } }, 'Use this folder')));
          }
        }
      }
      const guess = check && check.ok ? check.name : (check && check.suggest ? lastSeg(check.suggest.path.replace(/\/design$/, '')) : lastSeg(p));
      nameIn.placeholder = guess || 'project';
    }
    async function runCheck() {
      const p = pathIn.value.trim();
      if (!p) { check = null; paint(); return; }
      const my = ++seq;
      const d = await post('/api/roots/check', { path: p, name: nameIn.value.trim() });
      if (my !== seq) return;
      check = Object.assign({}, d, { path: p });
      paint();
    }
    function changed(now) {
      check = null;
      paint();
      clearTimeout(timer);
      timer = setTimeout(runCheck, now ? 0 : 300);
    }
    async function submit() {
      if (addBtn.disabled) return;
      busy = true; paint();
      const d = await post('/api/roots/add', { path: pathIn.value.trim(), name: nameIn.value.trim() || undefined });
      busy = false;
      if (!d.ok) { check = { ok: false, error: d.error || 'Could not add', path: pathIn.value.trim() }; paint(); return; }
      close();
      MC.toast('Added ' + d.name);
      await MC.refresh(true);
      MC.go({ project: d.name, page: 'ideas', filter: null, q: '' }, true);
    }
    pathIn.addEventListener('input', () => changed(false));
    nameIn.addEventListener('input', () => { if (pathIn.value.trim()) changed(false); else paint(); });
    pathIn.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); if (check && check.ok) submit(); else changed(true); } });
    nameIn.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); submit(); } });
    addBtn.addEventListener('click', submit);

    // Find in folders
    function scanChecked() { return [...scanList.querySelectorAll('input:checked:not(:disabled)')]; }
    function paintSel() {
      const n = scanChecked().length;
      addSel.disabled = !n;
      addSel.textContent = n ? 'Add ' + MC.plural(n, 'project') : 'Add selected';
    }
    async function scan() {
      const dirs = scanIn.value.split(',').map((s) => s.trim()).filter(Boolean);
      scanList.textContent = '';
      if (!dirs.length) { scanMsg.textContent = 'Enter a folder to search'; return; }
      scanMsg.textContent = 'Searching...';
      scanBtn.disabled = true;
      const d = await post('/api/roots/scan', { dirs });
      scanBtn.disabled = false;
      if (!d.ok) { scanMsg.textContent = d.error || 'Search failed'; paintSel(); return; }
      const found = d.found || [];
      scanMsg.textContent = found.length ? 'Found ' + MC.plural(found.length, 'design folder') : 'No design folders found';
      found.forEach((it, i) => {
        const cb = h('input', { type: 'checkbox', id: 'scan-cb-' + i });
        cb.checked = !it.already_registered;
        cb.disabled = !!it.already_registered;
        cb._it = it;
        cb.addEventListener('change', paintSel);
        scanList.append(h('label', { class: 'scanitem', for: 'scan-cb-' + i }, cb,
          h('span', { class: 'nm' }, h('span', { text: it.name }), h('span', { class: 'mono', text: it.path })),
          it.already_registered ? h('span', { class: 'tag', text: 'already registered' }) : null));
      });
      paintSel();
    }
    async function addScanned() {
      const cbs = scanChecked();
      if (!cbs.length) return;
      addSel.disabled = true;
      let added = 0, last = '';
      const errors = [];
      for (const cb of cbs) {
        const d = await post('/api/roots/add', { path: cb._it.path, name: cb._it.name });
        if (d.ok) { added++; last = d.name; cb.checked = false; cb.disabled = true; }
        else errors.push(cb._it.name + ': ' + (d.error || 'failed'));
      }
      if (errors.length) { scanMsg.textContent = errors.join(' / '); paintSel(); if (!added) return; }
      if (added) {
        if (!errors.length) close();
        MC.toast('Added ' + MC.plural(added, 'project'));
        await MC.refresh(true);
        MC.go(added === 1 ? { project: last, page: 'ideas', filter: null, q: '' } : { project: 'all', page: 'ideas' }, true);
      }
    }
    scanBtn.addEventListener('click', scan);
    scanIn.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); scan(); } });
    addSel.addEventListener('click', addScanned);

    paint();
    if (pathIn.value.trim()) runCheck();
    (tab === 'path' ? pathIn : scanIn).focus();
  }

  window.MC_MANAGE = {
    openAdd,
    topbar() {
      return [
        h('button', { class: 'btn sm tb-narrow', type: 'button', onclick: () => openAdd() }, icon('plus', 'sm'), 'Add project'),
        h('button', { class: 'icon-btn tb-phone', type: 'button', 'aria-label': 'Add project', onclick: () => openAdd() }, icon('plus')),
      ];
    },
    railFoot() {
      return [
        h('button', { class: 'btn', type: 'button', onclick: () => openAdd() }, icon('plus'), 'Add project'),
        h('button', { class: 'btn ghost', type: 'button', onclick: () => openAdd({ tab: 'find' }) }, icon('folder-search'), 'Find in folders'),
      ];
    },
    revealButton(x) {
      return h('button', { class: 'btn sm', type: 'button', onclick: (e) => { e.preventDefault(); reveal(x.project, x.name); } },
        icon('folder', 'sm'), 'Reveal');
    },
    cardMenuItems(x) {
      const items = [
        { icon: 'folder', label: 'Copy path', run: () => MC.copy(ideaPath(x), 'Path copied') },
        { icon: 'folder-search', label: 'Reveal in Finder', run: () => reveal(x.project, x.name) },
      ];
      if (collections()) {
        items.push({ icon: 'layers', label: 'Move to collection', keep: true, more: true, run: () => {
          const menu = MC.menu, saved = [...menu.childNodes], label = menu.getAttribute('aria-label');
          // An idea that is in only because its whole project is cannot be taken out on its own
          const target = { key: x.project + '/' + x.name, name: x.name, current: x.colWhole ? null : x.col, removable: !!x.col && !x.colWhole };
          const back = () => {
            menu.replaceChildren(...saved); menu.setAttribute('aria-label', label); menu.classList.remove('cols'); menu._back = null;
            const f = menu.querySelector('.has-more'); if (f) f.focus({ preventScroll: true });
          };
          collectionList(menu, target, 'Move to collection', back);
        } });
      }
      return items;
    },
    projectTools(p, rescan) {
      const more = h('button', { class: 'icon-btn sm', type: 'button', 'aria-label': 'Project menu', 'aria-haspopup': 'menu' }, icon('dots'));
      more.addEventListener('click', () => {
        const items = [
          { icon: 'edit', label: 'Rename', run: () => renameProject(p.name) },
          { icon: 'x', label: 'Remove from list', danger: true, run: () => removeProject(p.name) },
        ];
        if (collections()) {
          items.splice(1, 0, { icon: 'layers', label: 'Add to collection', keep: true, more: true, run: () => {
            const saved = [...m.childNodes];
            const cur = MC.collectionOf(p.name);
            const back = () => {
              m.replaceChildren(...saved); m.setAttribute('aria-label', 'Project actions'); m.classList.remove('cols'); m._back = null;
              const f = m.querySelector('.has-more'); if (f) f.focus({ preventScroll: true });
            };
            collectionList(m, { key: p.name, name: p.name, current: cur, removable: !!cur }, 'Add ' + p.name + ' to collection', back);
          } });
        }
        const m = MC.buildMenu(items, 'Project actions');
        m.style.top = (more.offsetTop + more.offsetHeight + 6) + 'px';
        m.style.right = '0';
        more.setAttribute('aria-expanded', 'true');
        MC.showMenu(more.parentNode, m, () => more.setAttribute('aria-expanded', 'false'));
      });
      return [h('button', { class: 'btn sm', type: 'button', onclick: () => reveal(p.name, '') }, icon('folder', 'sm'), 'Reveal in Finder'), rescan, more];
    },
    newIdeaCard(p) {
      const cmd = 'canvas new ' + (p.path ? MC.shq(p.path) : '<design dir>') + ' <idea>';
      return h('div', { class: 'add-idea' }, h('span', { class: 'ic' }, icon('terminal')), h('b', { text: 'New idea in ' + p.name }),
        h('span', { class: 'mono', text: cmd }),
        h('button', { class: 'btn sm ghost', type: 'button', onclick: () => MC.copy(cmd, 'Command copied') }, 'Copy'));
    },
    missingActions(p) {
      return [
        h('button', { class: 'btn primary', type: 'button', onclick: () => openAdd({ path: p.path, name: p.name }) }, icon('folder-search'), 'Locate folder'),
        h('button', { class: 'btn', type: 'button', onclick: async () => {
          await MC.refresh(true);
          const now = project(p.name);
          MC.toast(now && !now.missing ? p.name + ' is back' : 'Still missing');
        } }, icon('refresh'), 'Check again'),
        h('button', { class: 'btn ghost', type: 'button', onclick: () => removeProject(p.name) }, 'Remove from list'),
      ];
    },
    emptyActions() {
      return [
        h('button', { class: 'btn primary', type: 'button', onclick: () => openAdd() }, icon('plus'), 'Add project'),
        h('button', { class: 'btn', type: 'button', onclick: () => openAdd({ tab: 'find' }) }, icon('folder-search'), 'Find in folders'),
      ];
    },
    paletteActions() {
      return [
        { icon: 'plus', label: 'Add project', run: () => openAdd() },
        { icon: 'folder-search', label: 'Find design folders', run: () => openAdd({ tab: 'find' }) },
      ];
    },
    noResultsActions() {
      return [
        h('button', { class: 'btn primary', type: 'button', onclick: () => { MC.closeLayer(); openAdd(); } }, icon('plus'), 'Add project'),
        h('button', { class: 'btn', type: 'button', onclick: () => { MC.closeLayer(); openAdd({ tab: 'find' }); } }, icon('folder-search'), 'Find design folders'),
      ];
    },
  };
})();
