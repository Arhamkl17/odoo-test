# -*- coding: utf-8 -*-
"""perbaikan_12_jejak_audit.py — F3: jejak audit nomor jurnal + period lock

KONTEKS PENTING (hasil inspeksi 15 Sep 2026)
--------------------------------------------
DB ini memakai modul OCA `account_move_name_sequence` (installed). Modul itu
mengganti mekanisme penomoran Odoo:
  * `name` dihitung dari `ir.sequence` milik jurnal (`journal.sequence_id`),
    dengan prefix ber-template, mis. `POSS/%(range_year)s/%(range_month)s/`;
  * `sequence_prefix`/`sequence_number` sengaja DIBIARKAN KOSONG kecuali jurnal
    memakai mode terkunci-hash (`restrict_mode_hash_table`) → jadi NULL di sini
    BUKAN cacat data;
  * `_constrains_date_sequence` dimatikan modul, dan wizard core
    `account.resequence.wizard` TIDAK kompatibel (gagal di constraint
    `account_move_name_state_diagonal`). Karena itu penomoran ulang di sini
    ditulis langsung ke `name` (wizard-nya tidak dipakai).

Temuan F3 yang diperbaiki:
  1. 146 entri jurnal POS bernomor `POSS/2026/09/0001..0146` padahal tanggal
     akuntansinya 19 Jun – 31 Agu 2026 → nama tidak ikut tanggal akuntansi.
  2. 28 nomor hilang di 7 jurnal (lihat keluaran [2] di bawah).
  3. Belum ada period lock → entri Jun–Agu 2026 masih bisa diubah.

Aksi:
  RESEQUENCE=1  → entri yang nama-nya tidak sesuai tanggal akuntansi dinomori
                  ulang per bulan mengikuti urutan tanggal (POS: 146 entri).
  CLOSE_GAPS=1  → opsional: rapatkan lubang nomor di 7 jurnal lain dengan tetap
                  mempertahankan urutan nama (nomor entri lama ikut berubah).
                  Default OFF: nomor yang sudah terbit tidak ditulis ulang,
                  lubangnya cukup didokumentasikan.
  LOCK=1        → set `fiscalyear_lock_date` (default 2026-08-31).
  UNLOCK=1      → kosongkan semua lock date.
  COUNTERS=1    → selaraskan `number_next` pada `ir.sequence.date_range` dengan
                  nomor terakhir yang benar-benar terpakai (+ buat date range
                  untuk bulan yang punya entri tapi belum punya range).

Catatan Odoo 19: lock date bersifat "postpone" — entri baru bertanggal <= lock
date otomatis DIGESER ke tanggal setelah lock. Jadi sebelum mengerjakan koreksi
periode (F4 dst.) jalankan UNLOCK=1 dulu, lalu LOCK=1 lagi setelah selesai.

Jalankan (default DRY-RUN):
  su odoo -s /bin/bash -c "odoo shell -d Test1 --no-http --db_host db \
    --db_port 5432 --db_user odoo --db_password odoo --log-level=warn" \
    < scripts/perbaikan_12_jejak_audit.py

Eksekusi:
  RESEQUENCE=1 COUNTERS=1 LOCK=1 su odoo -s /bin/bash -c "... odoo shell ..." \
    < scripts/perbaikan_12_jejak_audit.py

Env: RESEQUENCE, CLOSE_GAPS, COUNTERS, LOCK, UNLOCK, LOCK_DATE, JOURNALS=KODE,...
"""
import os
import re
import calendar
import datetime
from collections import defaultdict

RUN_RESEQ = os.environ.get("RESEQUENCE") == "1"
RUN_CLOSE = os.environ.get("CLOSE_GAPS") == "1"
RUN_COUNTERS = os.environ.get("COUNTERS") == "1"
RUN_LOCK = os.environ.get("LOCK") == "1"
RUN_UNLOCK = os.environ.get("UNLOCK") == "1"
LOCK_DATE = os.environ.get("LOCK_DATE", "2026-08-31")
ONLY = [j.strip() for j in os.environ.get("JOURNALS", "").split(",") if j.strip()]
DRY = not (RUN_RESEQ or RUN_CLOSE or RUN_COUNTERS or RUN_LOCK or RUN_UNLOCK)

cr = env.cr
AM = env["account.move"]
SEQ = env["ir.sequence"]
say = lambda m="": print(m)
money = lambda x: "{:,.2f}".format(float(x or 0))
NAME_RE = re.compile(r"^(?P<pref>.+?)/(?P<year>\d{4})(?:/(?P<month>\d{2}))?/(?P<seq>\d+)$")
PAD = lambda name: len(NAME_RE.match(name).group("seq"))
PREFIX_OF = lambda name: re.sub(r"\d+$", "", name)      # 'MISC/2026/06/'


def render(seq, day):
    """Prefix & suffix aktual dari ir.sequence untuk tanggal tertentu."""
    s = day.strftime("%Y-%m-%d %H:%M:%S")
    return seq._get_prefix_suffix(date=s, date_range=s)


def new_name(seq, day, n):
    prefix, suffix = render(seq, day)
    return "%s%s%s" % (prefix, str(n).zfill(seq.padding or 4), suffix or "")


say("=" * 112)
say("F3 — JEJAK AUDIT (nomor jurnal) & PERIOD LOCK")
say("  resequence=%s close_gaps=%s counters=%s lock=%s unlock=%s lock_date=%s%s"
    % (RUN_RESEQ, RUN_CLOSE, RUN_COUNTERS, RUN_LOCK, RUN_UNLOCK, LOCK_DATE,
       "   [DRY-RUN]" if DRY else ""))
if ONLY:
    say("  dibatasi ke jurnal: %s" % ", ".join(ONLY))
say("=" * 112)

# ------------------------------------------------------------------ 1) diagnosa
cr.execute("""
    SELECT m.id, m.name, m.date, j.id, j.code
    FROM account_move m JOIN account_journal j ON j.id = m.journal_id
    WHERE m.name IS NOT NULL AND m.name != '/' AND m.state = 'posted'
    ORDER BY j.code, m.date, m.id
""")
by_journal = defaultdict(list)
for mid, name, date, jid, jcode in cr.fetchall():
    by_journal[(jid, jcode)].append({"id": mid, "name": name, "date": date})

say("")
say("[1] Diagnosa penomoran (berdasarkan nama entri)")
say("%-7s %6s %12s %9s %-22s %-22s" % ("JURNAL", "ENTRI", "NAMA≠TANGGAL", "LUBANG", "NOMOR PERTAMA", "NOMOR TERAKHIR"))
say("-" * 112)
renumber = {}     # jurnal dgn nama tidak sesuai tanggal akuntansi
gaps = {}         # jurnal dgn lubang nomor
total_bad = 0
for (jid, jcode), moves in sorted(by_journal.items(), key=lambda kv: kv[0][1]):
    if ONLY and jcode not in ONLY:
        continue
    bad = 0
    groups = defaultdict(list)
    for m in moves:
        mt = NAME_RE.match(m["name"])
        if not mt:
            continue
        groups[(mt.group("pref"), mt.group("year"), mt.group("month"))].append(m)
        if mt.group("year") != m["date"].strftime("%Y") or (
                mt.group("month") and mt.group("month") != m["date"].strftime("%m")):
            bad += 1
    missing = []
    for g, items in sorted(groups.items()):
        nums = sorted(int(NAME_RE.match(i["name"]).group("seq")) for i in items)
        missing += [(g, x) for x in range(nums[0], nums[-1] + 1) if x not in nums]
    total_bad += bad
    if bad:
        renumber[(jid, jcode)] = groups
    if missing:
        gaps[(jid, jcode)] = missing
    say("%-7s %6d %12d %9d %-22s %-22s%s" % (
        jcode, len(moves), bad, len(missing),
        min(m["name"] for m in moves), max(m["name"] for m in moves),
        ("  <== RESEQUENCE (tanggal)" if bad else "") + ("  <== ada lubang" if missing else "")))
say("-" * 112)
say("  TOTAL %d entri · %d nama tidak ikut tanggal akuntansi (jurnal: %s) · %d nomor hilang di %d jurnal"
    % (sum(len(v) for v in by_journal.values()), total_bad,
       ", ".join(j for _i, j in renumber) or "-", sum(len(v) for v in gaps.values()), len(gaps)))

say("")
say("[2] Daftar nomor hilang (didokumentasikan)")
for (jid, jcode), missing in sorted(gaps.items(), key=lambda kv: kv[0][1]):
    per = defaultdict(list)
    for g, x in missing:
        per["/".join([y for y in g if y])].append(x)
    for pref, xs in sorted(per.items()):
        say("      %-24s %2d nomor : %s" % (pref + "/", len(xs), ", ".join(str(x) for x in xs)))

# ------------------------------------------------------------------ 3) preview
say("")
say("[3] Rencana penomoran ulang (mengikuti tanggal akuntansi)")
plan = {}
for (jid, jcode), groups in sorted(renumber.items(), key=lambda kv: kv[0][1]):
    seq = env["account.journal"].browse(jid).sequence_id
    per_month = defaultdict(list)
    for g, items in groups.items():
        for m in items:
            per_month[(m["date"].year, m["date"].month)].append(m)
    plan[(jid, jcode)] = per_month
    for (y, mo), items in sorted(per_month.items()):
        items.sort(key=lambda m: (m["date"], m["id"]))
        say("      %-7s %s/%02d : %3d entri  %s … %s   (sequence: %s)"
            % (jcode, y, mo, len(items), new_name(seq, items[0]["date"], 1),
               new_name(seq, items[-1]["date"], len(items)), seq.display_name))

say("")
say("[4] Status penghitung ir.sequence (nomor terpakai vs number_next)")
say("%-7s %-24s %-24s %-10s %-10s" % ("JURNAL", "SEQUENCE", "RANGE", "TERPAKAI", "NUMBER_NEXT"))
say("-" * 112)
for (jid, jcode), moves in sorted(by_journal.items(), key=lambda kv: kv[0][1]):
    if ONLY and jcode not in ONLY:
        continue
    seq = env["account.journal"].browse(jid).sequence_id
    if not seq:
        say("%-7s (belum punya ir.sequence)" % jcode)
        continue
    ranges = seq.date_range_ids.sorted("date_from") or [None]
    for r in ranges:
        lo, hi = (r.date_from, r.date_to) if r else (None, None)
        mx = 0
        for m in moves:
            if lo and not (lo <= m["date"] <= hi):
                continue
            mt = NAME_RE.match(m["name"])
            if mt:
                mx = max(mx, int(mt.group("seq")))
        nxt = r.number_next if r else seq.number_next_actual
        say("%-7s %-24s %-24s %-10d %-10d%s" % (
            jcode, seq.display_name[:24],
            "%s..%s" % (lo, hi) if lo else "(tanpa range)", mx, nxt,
            "   <== akan diselaraskan" if (RUN_COUNTERS or RUN_RESEQ or RUN_CLOSE) and nxt != mx + 1 else ""))

if DRY:
    company = env.company
    say("")
    say("[5] Lock date saat ini: global=%s tax=%s sales=%s purchase=%s hard=%s"
        % (company.fiscalyear_lock_date, company.tax_lock_date, company.sale_lock_date,
           company.purchase_lock_date, company.hard_lock_date))
    say("")
    say("DRY-RUN — tidak ada data ditulis.")
    say("Eksekusi: RESEQUENCE=1 COUNTERS=1 LOCK=1")
    import sys
    sys.exit(0)


def sync_counters(jid, jcode):
    """Selaraskan number_next tiap ir.sequence.date_range + buat range yang belum ada."""
    seq = env["account.journal"].browse(jid).sequence_id
    if not seq:
        return 0
    moves = AM.search([("journal_id", "=", jid), ("state", "=", "posted"), ("name", "!=", "/")])
    touched = 0

    def max_used(lo, hi):
        mx = 0
        for m in moves:
            if lo and not (lo <= m.date <= hi):
                continue
            prefix, _suffix = render(seq, m.date)
            if m.name.startswith(prefix):
                rest = m.name[len(prefix):]
                if rest.isdigit():
                    mx = max(mx, int(rest))
        return mx

    ranges = list(seq.date_range_ids)
    # buat date range untuk bulan yang punya entri tapi belum punya range
    months = sorted({(m.date.year, m.date.month) for m in moves})
    for (y, mo) in months:
        lo = datetime.date(y, mo, 1)
        hi = datetime.date(y, mo, calendar.monthrange(y, mo)[1])
        if not [r for r in ranges if r.date_from <= lo <= r.date_to]:
            r = env["ir.sequence.date_range"].create({"sequence_id": seq.id, "date_from": lo, "date_to": hi})
            ranges.append(r)
            say("      %-7s + date_range %s..%s (dibuat)" % (jcode, lo, hi))
    # selaraskan SEMUA range (yang kosong dikembalikan ke 1)
    for r in ranges:
        mx = max_used(r.date_from, r.date_to)
        target = mx + 1 if mx else 1
        if r.number_next != target:
            r.number_next = target
            touched += 1
            say("      %-7s   number_next %-24s = %d (nomor terpakai maks %d)"
                % (jcode, "%s..%s" % (r.date_from, r.date_to), target, mx))
    return touched


def rename_group(moves, namer):
    """Ganti nama dua tahap agar tidak menabrak unique index (name, journal_id)."""
    for m in moves:
        m.name = "F3TMP/%04d/%06d" % (m.journal_id.id, m.id)
    moves.flush_recordset(["name"])
    for m in moves:
        m.name = namer(m)
    moves.flush_recordset(["name"])


# ------------------------------------------------------------------ EKSEKUSI
for (jid, jcode), per_month in sorted(plan.items(), key=lambda kv: kv[0][1]):
    seq = env["account.journal"].browse(jid).sequence_id
    say("")
    say("[6] RESEQUENCE %s — %d entri dinomori ulang mengikuti tanggal akuntansi" % (jcode, sum(len(v) for v in per_month.values())))
    for (y, mo), items in sorted(per_month.items()):
        items.sort(key=lambda m: (m["date"], m["id"]))
        recs = AM.browse([m["id"] for m in items])
        order = {m["id"]: i + 1 for i, m in enumerate(items)}
        rename_group(recs, lambda m: new_name(seq, m.date, order[m.id]))
        env.cr.commit()
        say("      %s/%02d : %s … %s" % (y, mo, new_name(seq, items[0]["date"], 1),
                                          new_name(seq, items[-1]["date"], len(items))))

if RUN_CLOSE:
    say("")
    say("[6b] CLOSE_GAPS — merapatkan lubang nomor (urutan nama dipertahankan)")
    for (jid, jcode), missing in sorted(gaps.items(), key=lambda kv: kv[0][1]):
        if (jid, jcode) in plan:
            continue
        seq = env["account.journal"].browse(jid).sequence_id
        moves = [m for m in by_journal[(jid, jcode)]]
        groups = defaultdict(list)
        for m in moves:
            groups[PREFIX_OF(m["name"])].append(m)
        for pref, items in sorted(groups.items()):
            items.sort(key=lambda m: int(NAME_RE.match(m["name"]).group("seq")))
            pad = PAD(items[0]["name"])
            old_first = items[0]["name"]
            old_last = items[-1]["name"]
            recs = AM.browse([m["id"] for m in items])
            order = {m["id"]: i + 1 for i, m in enumerate(items)}
            rename_group(recs, lambda m: "%s%s" % (pref, str(order[m.id]).zfill(pad)))
            env.cr.commit()
            say("      %-7s %-24s %3d entri · %s→%s  %s→%s" % (
                jcode, pref, len(items), old_first, pref + str(1).zfill(pad),
                old_last, pref + str(len(items)).zfill(pad)))

if RUN_COUNTERS or RUN_RESEQ or RUN_CLOSE:
    say("")
    say("[7] Penyelarasan penghitung ir.sequence (idempotent, semua jurnal)")
    for (jid, jcode) in sorted(by_journal, key=lambda k: k[1]):
        if ONLY and jcode not in ONLY:
            continue
        n = sync_counters(jid, jcode)
        env.cr.commit()
        if not n:
            say("      %-7s sudah selaras" % jcode)

company = env.company
if RUN_UNLOCK:
    say("")
    say("[8] UNLOCK — mengosongkan semua lock date")
    company.write({"fiscalyear_lock_date": False, "tax_lock_date": False,
                   "sale_lock_date": False, "purchase_lock_date": False})
    env.cr.commit()
if RUN_LOCK:
    say("")
    say("[8] LOCK — global lock date = %s" % LOCK_DATE)
    company.write({"fiscalyear_lock_date": LOCK_DATE})
    env.cr.commit()

# ------------------------------------------------------------------ VERIFIKASI
say("")
say("[9] Verifikasi")
cr.execute("""
    SELECT j.code, COUNT(*),
           COUNT(*) FILTER (WHERE (regexp_match(m.name, '/([0-9]{4})/'))[1] <> to_char(m.date,'YYYY')),
           COUNT(*) FILTER (WHERE m.name ~ '/[0-9]{4}/[0-9]{2}/'
                              AND (regexp_match(m.name, '/([0-9]{4})/([0-9]{2})/'))[2] <> to_char(m.date,'MM'))
    FROM account_move m JOIN account_journal j ON j.id = m.journal_id
    WHERE m.name IS NOT NULL AND m.name != '/' AND m.state = 'posted'
    GROUP BY j.code ORDER BY j.code
""")
say("%-7s %6s %12s %12s" % ("JURNAL", "ENTRI", "NAMA≠TAHUN", "NAMA≠BULAN"))
t_bad = 0
for jcode, n, by, bm in cr.fetchall():
    t_bad += by + bm
    say("%-7s %6d %12d %12d%s" % (jcode, n, by, bm, "   <<<" if (by or bm) else ""))
say("  total nama tidak sesuai tanggal: %d" % t_bad)
cr.execute("""SELECT journal_id, name, count(*) FROM account_move
              WHERE state='posted' AND name != '/' GROUP BY 1,2 HAVING count(*) > 1""")
dup = cr.fetchall()
say("  duplikasi nomor dalam jurnal yang sama: %d %s" % (len(dup), dup[:3] if dup else ""))
cr.execute("""SELECT COALESCE(SUM(aml.debit),0), COALESCE(SUM(aml.credit),0)
              FROM account_move_line aml JOIN account_move am ON am.id = aml.move_id
              WHERE am.state='posted'""")
d, k = cr.fetchone()
say("  TB debit %s = credit %s (diff %s)" % (money(d), money(k), money(float(d or 0) - float(k or 0))))
cr.execute("""SELECT COALESCE(SUM(aml.balance),0) FROM account_move_line aml
              JOIN account_move am ON am.id = aml.move_id
              JOIN account_account aa ON aa.id = aml.account_id
              WHERE am.state='posted' AND am.date BETWEEN '2026-08-01' AND '2026-08-31'
                AND aa.code_store->>'1' LIKE '5%'""")
hpp = cr.fetchone()[0]
say("  HPP Agustus (akun 5 persen) : %s   (acuan pasca F1/F2: 449.863.602,21)" % money(hpp))
say("  lock date: global=%s tax=%s sales=%s purchase=%s hard=%s"
    % (company.fiscalyear_lock_date, company.tax_lock_date, company.sale_lock_date,
       company.purchase_lock_date, company.hard_lock_date))
say("=" * 112)
