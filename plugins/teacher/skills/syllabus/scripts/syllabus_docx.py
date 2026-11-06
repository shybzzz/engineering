#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""syllabus_docx.py - inspect / extract / build a university syllabus .docx from a template.

Assumed layout (the common Ukrainian "силабус" form):
  * title-page paragraphs,
  * an "info" table: label column | content column, one row per section,
  * a "scheme" table (СХЕМА КУРСУ): header row + one row per class.

Subcommands
  inspect  <docx>                              paragraph indices, tables, widths, fonts
  extract  <docx> <content.json>               dump an existing syllabus into the content format
  build    <template.docx> <content.json> <out.docx> [--strict]
  selftest                                     build from a synthetic template and verify

Content format: see the "Content file" section of SKILL.md next to this script.
Requires: python-docx.
"""
import argparse
import copy
import io
import json
import os
import re
import shutil
import sys
import tempfile

import docx
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

URL_RE = re.compile(r'(https?://[^\s,;)\]]*[^\s,;)\].])')
MARK_RE = re.compile(r'(\*\*.+?\*\*|\[\[.+?\]\])')
LIT_RE = re.compile(r'\{\{lit:([^}]*)\}\}')
PLACEHOLDER_RE = re.compile(r'\[\[(.+?)\]\]')
YEAR_RE = re.compile(r'(?<![\d-])(19\d\d|20\d\d)(?![\d-])')

DEFAULTS = {
    'info_table': 0,            # index of the info table in the template
    'scheme_table': 1,          # index of the scheme table
    'label_kind': 'center',     # alignment of the label column
    'label_bold': True,
    'scheme_align': None,       # per-column paragraph kind; default: justify, last column centred
    'scheme_widths': None,      # per-column widths in twips; must keep the template's total
    'keep_rows_together': True,  # scheme rows do not split across pages
    'form_col': 2,              # scheme column holding the activity form (Лекція, ...)
    'hours_col': 4,             # scheme column holding the hours of the class
    'hours': None,              # expected hours per activity form, e.g. {"Лекція": 32}
    'year': None,               # approval year of the syllabus, for the literature age check
    'core_group': 'core',
    'core_count': 5,
    'core_max_age': 5,
    'lit_min': 15,
    'lit_max': 20,
    'lit_group_titles': {'core': 'Основна література:', 'extra': 'Додаткова література:',
                         'web': 'Інтернет-ресурси:'},
    'forbidden': [],            # strings from the template that must not survive in the output
}


def el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn('w:' + k), str(v))
    return e


def detect_font(node, default_size):
    """Font name and size (half-points) of the first formatted run under node."""
    for r in node.iter(qn('w:r')):
        rpr = r.find(qn('w:rPr'))
        if rpr is None:
            continue
        sz, rf = rpr.find(qn('w:sz')), rpr.find(qn('w:rFonts'))
        size = int(sz.get(qn('w:val'))) if sz is not None else None
        font = rf.get(qn('w:ascii')) if rf is not None else None
        if size or font:
            return font or 'Times New Roman', size or default_size
    return 'Times New Roman', default_size


def cells_of(tr):
    return tr.findall(qn('w:tc'))


def plain(cell):
    """Plain text of a content cell spec (str | dict | list)."""
    if isinstance(cell, str):
        return cell
    if isinstance(cell, dict):
        return cell.get('text', '')
    return ' '.join(plain(c) for c in cell)


class Builder:
    def __init__(self, template, content):
        self.d = docx.Document(template)
        self.c = content
        self.opt = dict(DEFAULTS)
        self.opt.update(content.get('options', {}))
        self.lit = content.get('literature', [])
        self.num = {}
        for i, e in enumerate(self.lit):
            if e['key'] in self.num:
                raise SystemExit(f"ERROR: duplicate literature key '{e['key']}'")
            self.num[e['key']] = i + 1
        self.cited = set()
        self.warnings = []
        self.placeholders = []

    # ---------- text ----------
    def resolve(self, text):
        def sub(m):
            keys = [k.strip() for k in m.group(1).split(',') if k.strip()]
            unknown = [k for k in keys if k not in self.num]
            if unknown:
                raise SystemExit(f'ERROR: unknown literature key(s) {unknown} in: {text[:80]}')
            self.cited.update(keys)
            return ', '.join(str(n) for n in sorted(self.num[k] for k in keys))
        text = LIT_RE.sub(sub, text)
        self.placeholders += PLACEHOLDER_RE.findall(text)
        return text

    def rpr(self, font, size, bold=False, highlight=False, link=False):
        r = el('w:rPr')
        r.append(el('w:rFonts', ascii=font, hAnsi=font, cs=font))
        if bold:
            r.append(el('w:b'))
            r.append(el('w:bCs'))
        if link:
            r.append(el('w:color', val='0563C1'))
        r.append(el('w:sz', val=size))
        r.append(el('w:szCs', val=size))
        if highlight:
            r.append(el('w:highlight', val='yellow'))
        if link:
            r.append(el('w:u', val='single'))
        return r

    def run(self, text, font, size, **kw):
        r = el('w:r')
        r.append(self.rpr(font, size, **kw))
        for i, part in enumerate(text.split('\t')):
            if i:
                r.append(el('w:tab'))
            if part:
                t = OxmlElement('w:t')
                t.text = part
                t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                r.append(t)
        return r

    def add_text(self, p, text, font, size, bold=False):
        """Runs for text with **bold**, [[placeholder]] (yellow) and auto-linked URLs."""
        for chunk in MARK_RE.split(text):
            if not chunk:
                continue
            b, hl = bold, False
            if chunk.startswith('**'):
                chunk, b = chunk[2:-2], True
            elif chunk.startswith('[['):
                chunk, hl = chunk[2:-2], True
            for piece in URL_RE.split(chunk):
                if not piece:
                    continue
                if URL_RE.fullmatch(piece):
                    rid = self.d.part.relate_to(piece, RT.HYPERLINK, is_external=True)
                    h = OxmlElement('w:hyperlink')
                    h.set(qn('r:id'), rid)
                    h.append(self.run(piece, font, size, bold=b, link=True))
                    p.append(h)
                else:
                    p.append(self.run(piece, font, size, bold=b, highlight=hl))

    def par(self, item, font, size):
        kind, text, bold, hanging = item
        p = el('w:p')
        ppr = el('w:pPr')
        ppr.append(el('w:spacing', after=0, line=240, lineRule='auto'))
        if hanging is None:
            hanging = {'num': 375, 'crit': 833}.get(kind)
        if hanging:
            ppr.append(el('w:ind', left=hanging, hanging=hanging))
        ppr.append(el('w:jc', val={'center': 'center', 'left': 'left'}.get(kind, 'both')))
        p.append(ppr)
        self.add_text(p, self.resolve(text), font, size, bold=bold)
        return p

    def items(self, cell, default_kind='body'):
        """Normalises a cell spec into [(kind, text, bold, hanging)]."""
        out = []
        for it in (cell if isinstance(cell, list) else [cell]):
            if isinstance(it, str):
                out.append((default_kind, it, False, None))
            elif it.get('literature'):
                out += self.literature_items()
            else:
                out.append((it.get('kind', default_kind), it.get('text', ''),
                            bool(it.get('bold')), it.get('hanging')))
        return out

    def literature_items(self):
        out, prev = [], None
        titles = self.opt['lit_group_titles']
        for e in self.lit:
            if e['group'] != prev:
                if prev is not None:
                    out.append(('body', '', False, None))
                out.append(('body', titles.get(e['group'], e['group']), False, None))
                prev = e['group']
            out.append(('num', f"{self.num[e['key']]}.\t{e['text']}", False, None))
        return out

    def fill(self, tc, items, font, size):
        for p in tc.findall(qn('w:p')):
            tc.remove(p)
        for it in items or [('body', '', False, None)]:
            tc.append(self.par(it, font, size))

    # ---------- parts ----------
    def title(self):
        pars = self.d.paragraphs
        for spec in self.c.get('title', []):
            if 'index' in spec:
                p = pars[spec['index']]
            else:
                hit = [q for q in pars if spec['contains'] in q.text]
                if not hit:
                    raise SystemExit(f"ERROR: no title paragraph contains '{spec['contains']}'")
                p = hit[0]
            runs = p.runs
            if runs:
                runs[0].text = self.resolve(spec['text'])
                for r in runs[1:]:
                    r._r.getparent().remove(r._r)
            else:
                p.add_run(self.resolve(spec['text']))

    def info(self):
        rows = self.c.get('info')
        if rows is None:
            return
        tbl = self.d.tables[self.opt['info_table']]._tbl
        trs = tbl.findall(qn('w:tr'))
        font, size = detect_font(cells_of(trs[0])[-1], 24)
        while len(trs) < len(rows):
            new = copy.deepcopy(trs[-1])
            trs[-1].addnext(new)
            trs.append(new)
        for tr in trs[len(rows):]:
            tbl.remove(tr)
        for tr, row in zip(trs, rows):
            tcs = cells_of(tr)
            if row.get('label') is not None:
                self.fill(tcs[0], [(self.opt['label_kind'], row['label'], self.opt['label_bold'], None)],
                          font, size)
            self.fill(tcs[-1], self.items(row.get('items', [])), font, size)

    def scheme(self):
        sch = self.c.get('scheme')
        if sch is None:
            return
        tbl = self.d.tables[self.opt['scheme_table']]._tbl
        trs = tbl.findall(qn('w:tr'))
        if len(trs) < 2:
            raise SystemExit('ERROR: the scheme table needs a header row and one body row as a prototype')
        proto = trs[1]
        ncol = len(cells_of(proto))
        font, size = detect_font(proto, 20)
        align = self.opt['scheme_align'] or (['both'] * (ncol - 1) + ['center'])
        for k, v in (sch.get('header') or {}).items():
            self.fill(cells_of(trs[0])[int(k)], [('center', v, False, None)], font, size)
        for tr in trs[2:]:
            tbl.remove(tr)
        anchor = proto
        for row in sch['rows']:
            if len(row) != ncol:
                raise SystemExit(f'ERROR: scheme row has {len(row)} cells, template has {ncol}: {row[:2]}')
            tr = copy.deepcopy(proto)
            for tc, cell, kind in zip(cells_of(tr), row, align):
                self.fill(tc, self.items(cell, kind), font, size)
            anchor.addnext(tr)
            anchor = tr
        tbl.remove(proto)

        widths = self.opt['scheme_widths']
        grid = tbl.find(qn('w:tblGrid')).findall(qn('w:gridCol'))
        if widths:
            old_total = sum(int(g.get(qn('w:w'))) for g in grid)
            if len(widths) != ncol:
                raise SystemExit(f'ERROR: scheme_widths has {len(widths)} values, template has {ncol} columns')
            if sum(widths) != old_total:
                self.warnings.append(f'scheme_widths sum {sum(widths)} differs from the template total {old_total}')
            for g, w in zip(grid, widths):
                g.set(qn('w:w'), str(w))
        for tr in tbl.findall(qn('w:tr')):
            if self.opt['keep_rows_together']:
                trpr = tr.get_or_add_trPr()
                if trpr.find(qn('w:cantSplit')) is None:
                    trpr.insert(0, el('w:cantSplit'))
            if widths:
                for tc, w in zip(cells_of(tr), widths):
                    tcpr = tc.get_or_add_tcPr()
                    tcw = tcpr.find(qn('w:tcW'))
                    if tcw is None:
                        tcw = el('w:tcW')
                        tcpr.insert(0, tcw)
                    tcw.set(qn('w:w'), str(w))
                    tcw.set(qn('w:type'), 'dxa')

    def metadata(self):
        meta = self.c.get('meta', {})
        cp = self.d.core_properties
        cp.title = meta.get('title', '')
        cp.author = meta.get('author', '')
        cp.last_modified_by = ''
        cp.subject = ''
        cp.keywords = ''
        pkg = self.d.part.package
        for rid, rel in list(pkg.rels.items()):
            if rel.reltype.endswith('/thumbnail'):   # preview of the template's first page
                del pkg.rels[rid]

    # ---------- checks ----------
    def check(self):
        o, w = self.opt, self.warnings
        if self.lit:
            n = len(self.lit)
            if not o['lit_min'] <= n <= o['lit_max']:
                w.append(f"literature has {n} entries, expected {o['lit_min']}-{o['lit_max']}")
            core = [e for e in self.lit if e['group'] == o['core_group']]
            if len(core) != o['core_count']:
                w.append(f"core literature has {len(core)} entries, expected {o['core_count']}")
            if [e['group'] for e in self.lit[:len(core)]] != [o['core_group']] * len(core):
                w.append('core literature entries are not the first entries of the list')
            if o['year']:
                for e in core:
                    text = re.sub(r'ISBN[\s\d–-]+', '', URL_RE.sub('', e['text']))
                    years = [int(y) for y in YEAR_RE.findall(text) if int(y) <= o['year'] + 1]
                    if not years:
                        w.append(f"core entry '{e['key']}': no publication year found")
                    elif max(years) < o['year'] - o['core_max_age']:
                        w.append(f"core entry '{e['key']}' is from {max(years)}: older than "
                                 f"{o['core_max_age']} years in {o['year']}")
            sch = self.c.get('scheme')
            if sch and self.cited:
                unused = [e['key'] for e in self.lit if e['key'] not in self.cited]
                if unused:
                    w.append(f'literature never cited in the scheme: {unused}')
        sch = self.c.get('scheme')
        if sch and o['hours']:
            got = {}
            for row in sch['rows']:
                form, hrs = plain(row[o['form_col']]).strip(), plain(row[o['hours_col']]).strip()
                if hrs.isdigit():
                    got[form] = got.get(form, 0) + int(hrs)
            for form, exp in o['hours'].items():
                if got.get(form, 0) != exp:
                    w.append(f"scheme has {got.get(form, 0)} h of '{form}', expected {exp}")
            for form in got:
                if form not in o['hours']:
                    w.append(f"scheme has an activity form '{form}' that 'hours' does not list")
        text = '\n'.join(p.text for p in self.d.paragraphs)
        for t in self.d.tables:
            text += '\n' + '\n'.join(c.text for r in t.rows for c in r.cells)
        low = text.lower()
        for s in o['forbidden']:
            if s.lower() in low:
                w.append(f"template text survived in the output: '{s}'")

    def build(self, out):
        self.title()
        self.info()
        self.scheme()
        self.metadata()
        self.check()
        self.d.save(out)
        return self


def cmd_build(a):
    with io.open(a.content, encoding='utf-8') as f:
        content = json.load(f)
    b = Builder(a.template, content).build(a.out)
    print(f'saved {a.out}')
    print(f"literature: {len(b.lit)} entries; scheme rows: {len((content.get('scheme') or {}).get('rows', []))}")
    for p in b.placeholders:
        print(f'PLACEHOLDER (yellow, to be filled in): {p}')
    for w in b.warnings:
        print(f'WARN: {w}')
    if b.warnings and a.strict:
        sys.exit(2)


def par_markup(p):
    text = p.text
    runs = [r for r in p.runs if r.text.strip()]
    if text.strip() and runs and all(r.bold for r in runs):
        return f'**{text}**'
    return text


def cell_spec(tc_cell, counters):
    out = []
    for p in tc_cell.paragraphs:
        ppr = p._p.pPr
        numpr = ppr.find(qn('w:numPr')) if ppr is not None else None
        text = par_markup(p)
        if numpr is not None and text.strip():
            nid = numpr.find(qn('w:numId')).get(qn('w:val'))
            counters[nid] = counters.get(nid, 0) + 1
            out.append({'kind': 'num', 'text': f'{counters[nid]}.\t{text}'})
        else:
            out.append(text)
    return out[0] if len(out) == 1 and isinstance(out[0], str) else out


def cmd_extract(a):
    d = docx.Document(a.docx)
    counters = {}
    content = {
        'meta': {'title': d.core_properties.title or '', 'author': d.core_properties.author or ''},
        'options': {'year': None, 'hours': None, 'forbidden': []},
        'title': [{'index': i, 'text': p.text} for i, p in enumerate(d.paragraphs) if p.text.strip()],
        'literature': [],
        'info': [],
        'scheme': {'rows': []},
    }
    if d.tables:
        for row in d.tables[0].rows:
            tcs = row.cells
            items = cell_spec(tcs[-1], counters)
            content['info'].append({'label': ' '.join(tcs[0].text.split()),
                                    'items': items if isinstance(items, list) else [items]})
    if len(d.tables) > 1:
        for row in list(d.tables[1].rows)[1:]:
            content['scheme']['rows'].append([cell_spec(c, counters) for c in row.cells])
    with io.open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(content, f, ensure_ascii=False, indent=1)
    print(f"saved {a.out}: {len(content['title'])} title paragraphs, {len(content['info'])} info rows, "
          f"{len(content['scheme']['rows'])} scheme rows")
    print('NOTE: auto-numbered lists were renumbered per list; check the numbers against the source.')


def cmd_inspect(a):
    d = docx.Document(a.docx)
    s = d.sections[0]
    print(f'page {s.page_width.twips}x{s.page_height.twips} twips; margins L{s.left_margin.twips} '
          f'R{s.right_margin.twips} T{s.top_margin.twips} B{s.bottom_margin.twips}')
    print('body order:', ' '.join(c.tag.split('}')[1] for c in d.element.body))
    print('--- paragraphs (index | font, half-points | text) ---')
    for i, p in enumerate(d.paragraphs):
        if p.text.strip():
            print(f'{i:3} | {detect_font(p._p, 0)} | {p.text[:90]}')
    for ti, t in enumerate(d.tables):
        grid = [g.get(qn('w:w')) for g in t._tbl.find(qn('w:tblGrid'))]
        print(f'--- table {ti}: {len(t.rows)} rows, grid {grid} (total {sum(int(g) for g in grid)}), '
              f'font {detect_font(t._tbl, 0)} ---')
        for ri, row in enumerate(t.rows):
            tcs = cells_of(row._tr)
            cells = [' '.join(c.text.split())[:38] for c in row.cells[:len(tcs)]]
            print(f'  {ri:2} | ' + ' | '.join(cells))


def cmd_selftest(a):
    tmp = tempfile.mkdtemp(prefix='syllabus_selftest_')
    tpl, out = os.path.join(tmp, 'template.docx'), os.path.join(tmp, 'out.docx')
    d = docx.Document()
    d.add_paragraph('UNIVERSITY')
    d.add_paragraph('(протокол № 1 від 1 січня 2000 р.)')
    d.add_paragraph('«Old course»,')
    t = d.add_table(rows=3, cols=2)
    for i, (k, v) in enumerate([('Назва дисципліни', 'Old course'), ('Література', 'old list'),
                                ('Опитування', 'old')]):
        t.rows[i].cells[0].text, t.rows[i].cells[1].text = k, v
    d.add_paragraph('СХЕМА КУРСУ')
    s = d.add_table(rows=3, cols=6)
    for i, h in enumerate(['Тиж.', 'Тема', 'Форма', 'Література', 'Завдання, год', 'Термін']):
        s.rows[0].cells[i].text = h
        s.rows[1].cells[i].text = 'old'
    d.save(tpl)
    total = sum(int(g.get(qn('w:w'))) for g in s._tbl.find(qn('w:tblGrid')))
    widths = [total // 6] * 5 + [total - 5 * (total // 6)]
    lit = [{'key': f'b{i}', 'group': 'core' if i < 2 else 'web',
            'text': f'Author {i}. Title. – City: Publisher, {2024 if i else 2010}. – 100 p.'} for i in range(3)]
    content = {
        'meta': {'title': 'Selftest'},
        'options': {'year': 2026, 'core_count': 2, 'lit_min': 3, 'lit_max': 3, 'scheme_widths': widths,
                    'hours': {'Лекція': 4, 'Практичне заняття': 2}, 'forbidden': ['Old course']},
        'title': [{'contains': 'протокол', 'text': '(протокол № 2 від 2 лютого 2026 р.)'},
                  {'index': 2, 'text': '«New course»,'}],
        'literature': lit,
        'info': [{'label': 'Назва дисципліни', 'items': ['New course [[code?]]']},
                 {'label': 'Література', 'items': [{'literature': True}]},
                 {'label': 'Сторінка', 'items': ['See https://example.org/course now']},
                 {'label': 'Опитування', 'items': ['**Bold:** text', {'kind': 'crit', 'text': '5 – ok'}]}],
        'scheme': {'header': {'4': 'Год'}, 'rows': [
            ['1', ['**Topic 1.**', 'Theses.'], 'Лекція', '{{lit:b1,b0}}', '2', 'Next'],
            ['2', '**Topic 2.**', 'Лекція', '{{lit:b2}}', '2', 'Next'],
            ['2', '**Lab 1.**', 'Практичне заняття', '{{lit:b0}}', '2', 'Schedule']]},
    }
    b = Builder(tpl, content).build(out)
    r = docx.Document(out)
    assert r.paragraphs[1].text == '(протокол № 2 від 2 лютого 2026 р.)', r.paragraphs[1].text
    assert r.paragraphs[2].text == '«New course»,'
    t0, t1 = r.tables
    assert len(t0.rows) == 4 and len(t1.rows) == 4, (len(t0.rows), len(t1.rows))
    assert t0.rows[1].cells[1].paragraphs[2].text == '2.\tAuthor 1. Title. – City: Publisher, 2024. – 100 p.'
    assert t0.rows[2].cells[1].text == 'See https://example.org/course now', t0.rows[2].cells[1].text
    assert t1.rows[1].cells[3].text == '1, 2' and t1.rows[0].cells[4].text == 'Год'
    assert r.element.xml.count('<w:hyperlink') == 1 and r.element.xml.count('w:highlight') == 1
    assert r.element.xml.count('w:cantSplit') == 4
    assert b.placeholders == ['code?'], b.placeholders
    assert len(b.warnings) == 1 and "'b0' is from 2010" in b.warnings[0], b.warnings
    assert 'Old course' not in '\n'.join(c.text for tb in r.tables for row in tb.rows for c in row.cells)
    ex = os.path.join(tmp, 'extracted.json')
    cmd_extract(argparse.Namespace(docx=out, out=ex))
    with io.open(ex, encoding='utf-8') as f:
        e = json.load(f)
    assert len(e['info']) == 4 and len(e['scheme']['rows']) == 3
    assert e['scheme']['rows'][0][1] == ['**Topic 1.**', 'Theses.'], e['scheme']['rows'][0][1]
    Builder(tpl, e).build(os.path.join(tmp, 'roundtrip.docx'))
    shutil.rmtree(tmp, ignore_errors=True)
    print('selftest ok')


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('inspect')
    p.add_argument('docx')
    p.set_defaults(fn=cmd_inspect)
    p = sub.add_parser('extract')
    p.add_argument('docx')
    p.add_argument('out')
    p.set_defaults(fn=cmd_extract)
    p = sub.add_parser('build')
    p.add_argument('template')
    p.add_argument('content')
    p.add_argument('out')
    p.add_argument('--strict', action='store_true', help='exit 2 when any check warns')
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser('selftest')
    p.set_defaults(fn=cmd_selftest)
    a = ap.parse_args()
    a.fn(a)


if __name__ == '__main__':
    main()
