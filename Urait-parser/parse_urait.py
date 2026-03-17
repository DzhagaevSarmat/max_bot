import html as html_lib
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://urait.ru/library/vo"
STATE_PATH = "vo_all.state"
OUT_PATH = "vo_all.rumarc"


def fetch_html(url: str, timeout_s: int = 40) -> str:
    """Скачиваем html страницы как текст."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            "Accept-Language": "ru,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return raw.decode("utf-8", "replace")


def normalize_text(s: str) -> str:
    """убираем html теги, сущности, приводим пробелы в порядок."""
    s = re.sub(r"<[^>]+>", " ", s)               # выкидываем теги
    s = html_lib.unescape(s)                     # декодируем &quot; и т.п.
    s = s.replace("\xa0", " ").replace("\u2009", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# <div class="buffer" id="book_...">Библиографическая строка</div>
BUFFER_RE = re.compile(
    r'<div\s+class=(?:"|\')buffer(?:"|\')\s+id=(?:"|\')book_([^"\']+)(?:"|\')\s*>(.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)

# ФИО в формате: Фамилия, И. О. (опционально третья инициала)
NAME_RE = re.compile(
    r"[А-ЯЁA-Z][А-ЯЁA-Zа-яёa-z\-]+,\s*[А-ЯЁA-Z]\.\s*[А-ЯЁA-Z]\.(?:\s*[А-ЯЁA-Z]\.)?"
)


def extract_biblio_blocks(page_html: str):
    """Вернуть список (id, чистый_текст_цитаты)."""
    blocks = []
    for rec_id, raw in BUFFER_RE.findall(page_html):
        blocks.append((rec_id.strip(), normalize_text(raw)))
    return blocks


def parse_biblio_text(biblio: str) -> dict:
    """
    Разобрать одну строку вида:
    'Автор. Заглавие : ... / ... — Москва : Издательство Юрайт, 2025. — 182 с. — (Серия). — ISBN ... — URL: ...'
    в простой словарь.
    """
    result: dict[str, str] = {}

    # URL
    m = re.search(r"\bURL:\s*(https?://\S+)", biblio)
    if m:
        result["url"] = m.group(1).rstrip(").,;")

    # ISBN
    m = re.search(r"\bISBN\s*([0-9Xx\-]+)", biblio.replace("ISBN", "ISBN "))
    if m:
        result["isbn"] = m.group(1).upper()

    # Место, издательство, год:  — Москва : Издательство Юрайт, 2025
    m = re.search(r"—\s*([^—:]+)\s*:\s*([^,]+)\s*,\s*(\d{4})\b", biblio)
    if m:
        result["place"] = m.group(1).strip().rstrip(".")
        result["publisher"] = m.group(2).strip().rstrip(".")
        result["year"] = m.group(3)

    # Страницы:  — 182 с.
    m = re.search(r"—\s*(\d+)\s*с\.", biblio)
    if m:
        result["pages"] = f"{m.group(1)} с."

    # Серия:  — (Высшее образование).
    m = re.search(r"—\s*\(([^)]+)\)\.", biblio)
    if m:
        result["series"] = m.group(1).strip()

    # Заглавие и ответственность – всё до первого " — " (большого тире)
    head = re.split(r"\s+—\s+", biblio, maxsplit=1)[0].strip().rstrip(".")

    # Делим по "/" на заглавие и ответственность
    title = head
    responsibility = ""
    if "/" in head:
        left, right = head.split("/", 1)
        title = left.strip().rstrip(".")
        responsibility = right.strip().rstrip(".")
    else:
        title = head

    result["title"] = title
    if responsibility:
        result["responsibility"] = responsibility

    # исходный текст для проверки
    result["source"] = biblio

    return result


def mrk_line(tag: str, indicators: str, subfields: list[tuple[str, str]]) -> str:
    """Собрать одну строку вида =200  1#$a...$f..."""
    ind = indicators if indicators else "  "
    parts = []
    for code, val in subfields:
        if val:
            parts.append(f"${code}{val}")
    return f"={tag}  {ind}{''.join(parts)}".rstrip()


def record_to_rumarc(rec_id: str, data: dict) -> str:
    lines: list[str] = []

    # 001 – идентификатор
    lines.append(mrk_line("001", "", [("a", rec_id)]))

    # 010 – ISBN
    if "isbn" in data:
        lines.append(mrk_line("010", "  ", [("a", data["isbn"])]))

    # 200 – заглавие и ответственность
    title_sfs: list[tuple[str, str]] = [("a", data.get("title", ""))]
    if "responsibility" in data:
        title_sfs.append(("f", data["responsibility"]))
    lines.append(mrk_line("200", "1#", title_sfs))

    # 210 – выходные данные
    pub_sfs: list[tuple[str, str]] = []
    if "place" in data:
        pub_sfs.append(("a", data["place"]))
    if "publisher" in data:
        pub_sfs.append(("c", data["publisher"]))
    if "year" in data:
        pub_sfs.append(("d", data["year"]))
    if pub_sfs:
        lines.append(mrk_line("210", "  ", pub_sfs))

    # 215 – физическое описание
    if "pages" in data:
        lines.append(mrk_line("215", "  ", [("a", data["pages"])]))

    # 225 – серия
    if "series" in data:
        lines.append(mrk_line("225", "  ", [("a", data["series"])]))

    # 700 / 701 – авторы (поиск ФИО в поле ответственности)
    responsibility = data.get("responsibility", "")
    authors = NAME_RE.findall(responsibility) if responsibility else []
    if authors:
        lines.append(mrk_line("700", "1#", [("a", authors[0])]))
        for author in authors[1:]:
            lines.append(mrk_line("701", "1#", [("a", author)]))

    # 856 – URL
    if "url" in data:
        lines.append(mrk_line("856", "40", [("u", data["url"])]))

    # 801 – сведения о записи
    lines.append(mrk_line("801", "  ", [("a", "RU"), ("b", "urait.ru"), ("c", "20260303")]))

    # 999 – исходная строка
    lines.append(mrk_line("999", "  ", [("a", data.get("source", ""))]))

    return "\n".join(lines) + "\n"


def detect_total_pages(html: str) -> int:
    """определяем максимальный номер страницы по ссылкам ?page=N в HTML."""
    nums = [int(n) for n in re.findall(r"[?&]page=(\d+)", html)]
    return max(nums) if nums else 1


def build_page_url(base_url: str, page: int) -> str:
    """ построение url для заданного номера страницы (page>=1)"""
    if page <= 1:
        return base_url
    parsed = urllib.parse.urlparse(base_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page)
    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def deduplicate_rumarc(in_path: str = OUT_PATH) -> tuple[int, int]:
    """
    Удалить дубликаты записей в ruMARC(MRK) файле.
    Ключ уникальности: 001$a (id) -> 856$u (url) -> 010$a (isbn) -> весь текст записи.
    Перезаписывает файл на месте через временный файл.
    Возвращает (kept, removed).
    """
    p = Path(in_path)
    if not p.exists():
        return 0, 0

    id_re = re.compile(r"^=001\s+.*?\$a(.+)\s*$")
    isbn_re = re.compile(r"^=010\s+.*?\$a(.+)\s*$")
    url_re = re.compile(r"^=856\s+.*?\$u(\S+)\s*$")

    tmp = p.with_suffix(p.suffix + ".tmp")
    seen: set[str] = set()
    kept = removed = 0

    def record_key(rec_lines: list[str]) -> str:
        rid = rurl = risbn = None
        for ln in rec_lines:
            m = id_re.match(ln)
            if m:
                rid = m.group(1).strip()
                break
        if not rid:
            for ln in rec_lines:
                m = url_re.match(ln)
                if m:
                    rurl = m.group(1).strip()
                    break
        if not rid and not rurl:
            for ln in rec_lines:
                m = isbn_re.match(ln)
                if m:
                    risbn = m.group(1).strip()
                    break
        if rid:
            return f"id:{rid}"
        if rurl:
            return f"url:{rurl}"
        if risbn:
            return f"isbn:{risbn}"
        return "rec:" + "\n".join(rec_lines).strip()

    def flush_record(outf, rec_lines: list[str]) -> None:
        nonlocal kept, removed
        if not rec_lines:
            return
        k = record_key(rec_lines)
        if k in seen:
            removed += 1
            return
        seen.add(k)
        kept += 1
        outf.write("\n".join(rec_lines).rstrip() + "\n\n")

    with p.open("r", encoding="utf-8", errors="ignore") as f_in, tmp.open(
        "w", encoding="utf-8", newline="\n"
    ) as f_out:
        rec: list[str] = []
        for line in f_in:
            line = line.rstrip("\n\r")
            if not line.strip():
                flush_record(f_out, rec)
                rec = []
                continue
            rec.append(line)
        flush_record(f_out, rec)

    tmp.replace(p)

    return kept, removed


def main() -> int:
    # сколько страниц уже было обработано ранее (если есть файл состояния)
    last_done = 0
    state_file = Path(STATE_PATH)
    if state_file.exists():
        try:
            txt = state_file.read_text(encoding="utf-8").strip()
            if txt:
                last_done = int(txt)
        except Exception:
            last_done = 0

    first_html = fetch_html(DEFAULT_URL)
    first_blocks = extract_biblio_blocks(first_html)
    if not first_blocks:
        raise SystemExit("На первой странице не найдено блоков. возможно, разметка сайта поменялась")

    total_pages = detect_total_pages(first_html)
    print(f"Всего страниц в каталоге: {total_pages}. Уже было спарсено ранее: {last_done}.")
    if last_done >= total_pages:
        print(f"Все страницы уже были спарсены ранее (всего {total_pages}). Новых страниц нет.")
        return 0

    # спрашиваем у пользователя, сколько страниц спарсить за этот запуск
    while True:
        raw = input(f"Сколько страниц спарсить за этот запуск? Введите число: ").strip()
        try:
            pages_chunk = int(raw)
        except ValueError:
            print("Нужно ввести целое число, попробуйте ещё раз.")
            continue
        if pages_chunk <= 0:
            print("Число страниц должно быть больше 0.")
            continue
        break

    # Начинаем измерение после ввода пользователя (чтобы не считать время ожидания ввода)
    start_ts = time.perf_counter()

    remaining = total_pages - last_done
    pages_to_do = min(remaining, pages_chunk)
    from_page = last_done + 1
    to_page = last_done + pages_to_do

    print(f"\nЭтот запуск обработает страницы с {from_page} по {to_page}.")

    total_records = 0
    out_path = Path(OUT_PATH)
    do_append = out_path.exists()

    mode = "a" if do_append else "w"

    with open(OUT_PATH, mode, encoding="utf-8", newline="\n") as f:
        for page in range(from_page, to_page + 1):
            if page == 1:
                html = first_html
                blocks = first_blocks
            else:
                page_url = build_page_url(DEFAULT_URL, page)
                html = fetch_html(page_url)
                blocks = extract_biblio_blocks(html)
                if not blocks:
                    # если на какой-то странице записи закончились, прекращаем цикл
                    break

            for rec_id, biblio in blocks:
                data = parse_biblio_text(biblio)
                f.write(record_to_rumarc(rec_id, data))
                f.write("\n")  # разделитель записей
                total_records += 1

    # обновляем файл состояния количеством обработанных страниц
    try:
        state_file.write_text(str(to_page), encoding="utf-8")
    except Exception:
        pass

    total_done_after = min(to_page, total_pages)
    elapsed = time.perf_counter() - start_ts

    msg = (
        f"\nOK: {total_records} записей, "
        f"страницы {from_page}-{to_page} -> {OUT_PATH} (mode={'append' if do_append else 'overwrite'}).\n"
        f"Всего спарсено страниц: {total_done_after} из {total_pages}.\n"
        f"Время выполнения: {elapsed:.2f} сек."
    )
    if total_done_after >= total_pages:
        msg += "\nВсе страницы каталога уже спарсены."

    print(msg)

    # (!) Если нужно делать проверку после каждого запуска, то нужно закомментировать нижнюю строчку
    if total_done_after >= total_pages:
        ans = input("Убрать дубликаты в vo_all.rumarc? (y/n): ").strip().lower()
        if ans in ("y", "yes", "д", "да"):
            kept, removed = deduplicate_rumarc(OUT_PATH)
            print(f"Дедупликация завершена. Оставлено записей: {kept}, удалено дубликатов: {removed}.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
