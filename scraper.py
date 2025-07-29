import requests
import json
import re
from bs4 import BeautifulSoup
from typing import Dict, Optional

def parse_itmo_program(url: str) -> Dict:
    """
    Парсит магистерскую программу ИТМО по URL.
    Извлекает данные из встроенного JSON (__NEXT_DATA__).
    
    Args:
        url (str): URL страницы программы, например:
                   https://abit.itmo.ru/program/master/ai
    
    Returns:
        dict: Словарь с данными о программе.
    
    Raises:
        ValueError: Если данные не найдены.
        requests.RequestException: Если ошибка сети.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'  # Явно указываем кодировку
        html_content = response.text
    except requests.RequestException as e:
        raise ValueError(f"Ошибка при загрузке страницы: {e}")

    # Пытаемся найти <script id="__NEXT_DATA__">
    soup = BeautifulSoup(html_content, 'html.parser')
    script_tag = soup.find('script', id='__NEXT_DATA__')

    if script_tag and script_tag.string:
        json_str = script_tag.string
    else:
        # Если тег не найден — ищем вручную по шаблону JSON
        pattern = r'<script[^>]*type\s*=\s*["\']application/json["\'][^>]*>(.*?)</script>'
        matches = re.findall(pattern, html_content, re.DOTALL)
        
        # Ищем тот, что содержит "props" и "__N_SSG"
        for match in matches:
            if '"props"' in match and '__N_SSG' in match:
                json_str = match
                break
        else:
            raise ValueError("Не удалось найти __NEXT_DATA__ или встроенный JSON с данными программы.")

    # Убираем HTML-сущности (если есть)
    json_str = json_str.strip()
    if json_str.startswith('<!--'):
        json_str = re.sub(r'^<!--(.*?)-->$', r'\1', json_str, flags=re.DOTALL).strip()

    # Распарсим JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        # Попробуем извлечь валидный JSON из строки
        try:
            # Иногда JSON обрезан — попробуем найти начало
            start = json_str.find('{"props":')
            end = json_str.rfind('}') + 1
            if start != -1 and end > start:
                clean_json = json_str[start:end]
                data = json.loads(clean_json)
            else:
                raise e
        except:
            raise ValueError(f"Не удалось распарсить JSON: {e}")

    # Извлекаем данные программы
    try:
        page_props = data.get("props", {}).get("pageProps", {})
        if not page_props:
            print("Не найден pageProps в данных")
        else:
            print("Есть pageProps в данных")
            print(page_props.keys())
            print(page_props['similarPrograms'])
        program_data = data['props']['pageProps']['apiProgram']
        program_data_2 = data['props']['pageProps']['jsonProgram']
        exam_dates = data['props']['pageProps'].get('examDates', [])
    except KeyError:
        raise ValueError("Структура данных не соответствует ожидаемой. Возможно, URL неверный.")

    # Формируем результат
    parsed = {
        "title": program_data.get("title", "Неизвестно"),
        "slug": program_data.get("slug", "Неизвестно"),
        "about": {
            "lead": program_data_2.get("about", {}).get("lead", ""),
            "desc": program_data_2.get("about", {}).get("desc", "")
        },
        "career": {
            "text": program_data_2.get("career", {}).get("lead", "")
        },
        "education_cost": program_data.get("educationCost", {}),
        "study_period": program_data.get("study", {}).get("label", ""),
        "language": program_data.get("language", ""),
        "academic_plan_url": program_data.get("academic_plan", ""),
        "direction_of_education": program_data.get("direction_of_education", ""),
        "direction_code": program_data.get("direction_code", ""),
        "faculty": program_data.get("faculties", [{}])[0].get("title", "Неизвестно"),
        "faculty_link": program_data.get("faculties", [{}])[0].get("link", ""),
        "manager": {
            "name": f"{page_props.get('supervisor', {}).get('firstName', '')} {page_props.get('supervisor', {}).get('middleName', '')} {page_props.get('supervisor', {}).get('lastName', '')}".strip(),
        },
        "team": [
            {
                "name": f"{member.get('firstName', '')} {member.get('middleName', '')} {member.get('lastName', '')} ".strip(),
                "position": member.get("positions", [{}])[0].get("position_name", "") if member.get("positions") else "",
                "degree": member.get("degree", "")
            }
            for member in page_props.get("team", [])
        ],
        "partners": [
            logo.split('/')[-1] for logo in program_data_2.get("careersImages", [])
        ],
        "scholarships": [
            {"name": "Государственная академическая стипендия", "amount": "До 4 100 рублей"},
            {"name": "Повышенная государственная академическая стипендия", "amount": "До 27 000 рублей"},
            {"name": "Стипендия Президента и Правительства РФ", "amount": "До 30 000 рублей"},
            {"name": "Именная стипендия Правительства Санкт-Петербурга", "amount": "7 000 рублей"},
            {"name": "Стипендия фонда Владимира Потанина", "amount": "25 000 рублей"},
            {"name": "Стипендия «Альфа-Шанс»", "amount": "До 300 000 рублей"}
        ],
        "admission_methods": [
            method.get("title", "") for method in page_props.get("admission", {}).get("items", [])
        ],
        "exam_dates": exam_dates,
        "social_links": program_data_2.get("social", {}),
        "video_links": [video["content"] for video in program_data_2.get("about", {}).get("video", [])],
        "similar_programs": 
           [
            {
                "title": prog.get("title", ""),
                "year": prog.get("year", ""),
                "direction_of_education": prog.get("direction_of_education", ""),
                "slug": prog.get("slug", ""),
            }
            for prog in page_props['similarPrograms']
        ]
    }

    return parsed


# === Пример использования ===
if __name__ == "__main__":
    urls = [
        "https://abit.itmo.ru/program/master/ai",
        "https://abit.itmo.ru/program/master/ai_product"
    ]

    for url in urls:
        try:
            print(f"\n🔍 Загрузка данных с: {url}")
            data = parse_itmo_program(url)
            filename = f"itmo_{data['slug']}_parsed.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ Данные сохранены в {filename}")
            print(f"📌 Название: {data['title']}")
            print(f"📅 Даты экзаменов: {len(data['exam_dates'])} шт.")
            print(f"👥 Команда: {len(data['team'])} человек")

        except Exception as e:
            print(f"❌ Ошибка при обработке {url}: {e}")
