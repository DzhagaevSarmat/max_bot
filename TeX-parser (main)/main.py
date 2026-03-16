import re


tex_file = "Gutnova-CP-maps-01.tex"

with open(tex_file, 'r', encoding='cp1251') as f:
    content = f.read()


lines = content.split('\n')
uncommented_lines = []
for line in lines:
    if '%' in line:
        line = line[:line.index('%')]
    uncommented_lines.append(line)


clean_content = '\n'.join(uncommented_lines)

cite_pattern = r'\\cite(?:\[[^\]]*\])?\{([^}]+)\}'
cites = re.findall(cite_pattern, clean_content)



all_cites = set()
for cite in cites:
    for key in cite.split(','):
        all_cites.add(key.strip())


#все записи в библиографии
bib_pattern = r'\\(?:bibitem|Bibitem|RBibitem)\{([^}]+)\}'
all_bibs = set(re.findall(bib_pattern, clean_content))


# записи, которые есть в библиографии, но нет в ссылкаъ
unused = [bib for bib in all_bibs if bib not in all_cites]


#############
print(f"Всего ссылок в тексте (без учета комментариев): {len(all_cites)}")
print(f"Всего записей в библиографии: {len(all_bibs)}")
print("-" * 40)


if unused:
    print(f"Найдено {len(unused)} записей без ссылок:")
    for i, bib in enumerate(unused, 1):
        print(f"{i}. {bib}")
else:
    print("Все записи используются.")


print("\n\n###################")
print("Для проверки:")

print("Ссылки в тексте:", sorted(all_cites))
print("Записи в библиографии:", sorted(all_bibs))
print("Не используются:", unused)
