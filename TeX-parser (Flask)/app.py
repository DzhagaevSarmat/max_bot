from flask import Flask, render_template, request
import re
import os
import webbrowser
import threading

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# создаем папку для загрузок если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def parse_tex_file(content):
    """Парсит .tex файл и возвращает результаты"""
    # удаляем комментарии
    lines = content.split('\n')
    uncommented_lines = []
    for line in lines:
        if '%' in line:
            line = line[:line.index('%')]
        uncommented_lines.append(line)

    clean_content = '\n'.join(uncommented_lines)

    # находим все ссылки в тексте (СОХРАНЯЕМ ПОРЯДОК)
    cite_pattern = r'\\cite(?:\[[^\]]*\])?\{([^}]+)\}'
    cites = re.findall(cite_pattern, clean_content)

    # СОХРАНЯЕМ ПОРЯДОК ссылок в тексте (используем list)
    all_cites_order = []
    all_cites_set = set()
    for cite in cites:
        for key in cite.split(','):
            key_stripped = key.strip()
            if key_stripped not in all_cites_set:
                all_cites_order.append(key_stripped)
                all_cites_set.add(key_stripped)

    # находим все записи в библиографии
    bib_pattern = r'\\(?:bibitem|Bibitem|RBibitem)\{([^}]+)\}'
    all_bibs = set(re.findall(bib_pattern, clean_content))

    # находим неиспользуемые (есть в библиографии, нет в ссылках)
    unused = [bib for bib in sorted(all_bibs) if bib not in all_cites_set]

    # находим отсутствующие (есть в ссылках, нет в библиографии) - В ПОРЯДКЕ ИЗ ТЕКСТА!
    missing = [cite for cite in all_cites_order if cite not in all_bibs]

    return {
        'total_cites': len(all_cites_set),
        'total_bibs': len(all_bibs),
        'unused': unused,
        'missing': missing,
        'all_cites': sorted(all_cites_set),
        'all_bibs': sorted(all_bibs)
    }


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html', result=None, error=None)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Обработка загруженного файла"""
    if 'file' not in request.files:
        return render_template('index.html', error='Файл не выбран', result=None)

    file = request.files['file']

    if file.filename == '':
        return render_template('index.html', error='Файл не выбран', result=None)

    if not file.filename.endswith('.tex'):
        return render_template('index.html', error='Пожалуйста, загрузите .tex файл', result=None)

    try:
        # читаем файл в разных кодировках
        content = None
        for enc in ['cp1251', 'utf-8', 'windows-1251', 'koi8-r']:
            try:
                file.seek(0)
                content = file.read().decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return render_template('index.html', error='Не удалось прочитать файл. Проверьте кодировку.', result=None)

        # парсим файл
        result = parse_tex_file(content)
        result['filename'] = file.filename

        return render_template('index.html', result=result, error=None)

    except Exception as e:
        return render_template('index.html', error=f'Ошибка при обработке файла: {str(e)}', result=None)


# автоматич. открытие браузера:
def open_browser():
    """Открывает браузер после запуска сервера"""
    # проверяем, что это основной процесс, а не перезагрузчик
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        webbrowser.open_new('http://127.0.0.1:5000')


if __name__ == '__main__':
    # открываем браузер только если это основной процесс
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        threading.Timer(1, open_browser).start()
    # запускаем Flask сервер
    app.run(debug=True, host='127.0.0.1', port=5000)