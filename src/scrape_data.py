import requests
from bs4 import BeautifulSoup
import yaml
import os
import time

current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_script_dir)
corpus_path = os.path.join(project_root, 'data', 'astronomy_corpus.yml')

def clean_text(text):
    """removes whitespace, newlines, and non-breaking spaces."""
    if not text: return ""
    return text.strip().replace('\n', ' ').replace('  ', ' ').replace('\xa0', ' ')

def scrape_cool_cosmos_text():
    url = "https://coolcosmos.ipac.caltech.edu/asks"
    headers = {'User-Agent': 'Mozilla/5.0 (Education Project)'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        qa_pairs = []
        
        containers = soup.find_all(class_='question_container')
        
        question_links = []
        if containers:
            for container in containers:
                list_items = container.find_all('li')
                for li in list_items:
                    a_tag = li.find('a')
                    if a_tag and 'href' in a_tag.attrs:
                        question_links.append(a_tag)
                        
        for link_tag in question_links:
            question_text = clean_text(link_tag.get_text()).lower()
            href = link_tag['href']
            
            if not href.startswith('http'):
                full_url = "https://coolcosmos.ipac.caltech.edu" + href
            else:
                full_url = href

            try:
                time.sleep(0.5)
                ans_response = requests.get(full_url, headers=headers, timeout=5)
                ans_soup = BeautifulSoup(ans_response.content, 'html.parser')
                
                answer_div = ans_soup.find(class_='raw')
                if not answer_div:
                    answer_div = ans_soup.find(class_='answer')
                
                if answer_div:
                    answer_text = clean_text(answer_div.get_text())
                    qa_pairs.append([question_text, answer_text])
                    print(f"   [text scraped] {question_text}")
                    
            except Exception as e:
                print(f"   [error] {question_text}: {e}")

        return qa_pairs

    except Exception as e:
        return []

def scrape_cool_cosmos_videos():
    """
    Scrapes the 'Videos' section.
    """
    url = "https://coolcosmos.ipac.caltech.edu/asks"
    headers = {'User-Agent': 'Mozilla/5.0 (Education Project)'}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        qa_pairs = []

        video_header = soup.find('h2', class_='title', string=lambda t: t and 'Videos' in t)
        
        if not video_header:
            return []

        video_list_container = video_header.find_next_sibling()
        
        if not video_list_container:
            return []

        video_links = video_list_container.find_all('a')
        
        for link in video_links:
            question_text = clean_text(link.get_text()).lower()
            href = link['href']
            
            if not href.startswith('http'):
                full_url = "https://coolcosmos.ipac.caltech.edu" + href
            else:
                full_url = href

            answer_text = f"I have a video explanation for that! You can watch it here: {full_url}"
            
            qa_pairs.append([question_text, answer_text])
            print(f"   [video scraped] {question_text}")

        return qa_pairs

    except Exception as e:
        return []

def scrape_nasa():
    url = "https://imagine.gsfc.nasa.gov/science/questions/"
    headers = {'User-Agent': 'Mozilla/5.0 (Education Project)'}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html.parser')
        qa_pairs = []
        
        main_content = soup.find('div', id='content')
        if not main_content: return []

        links = main_content.find_all('a')
        for link in links:
            q_text = clean_text(link.get_text()).lower()
            href = link.get('href')
            
            if "?" in q_text and href:
                if not href.startswith('http'):
                    href = "https://imagine.gsfc.nasa.gov/science/questions/" + href
                
                time.sleep(0.5)
                ans_resp = requests.get(href, headers=headers)
                ans_soup = BeautifulSoup(ans_resp.content, 'html.parser')
                
                ans_content = ans_soup.find('div', id='content')
                if ans_content:
                    paragraphs = ans_content.find_all('p')
                    if paragraphs:
                        full_ans = " ".join([p.get_text() for p in paragraphs[:2]])
                        full_ans = clean_text(full_ans)
                        qa_pairs.append([q_text, full_ans])
                        print(f"   [NASA scraped] {q_text}")
        return qa_pairs
    except Exception as e:
        return []

if __name__ == "__main__":    
    text_data = scrape_cool_cosmos_text()
    video_data = scrape_cool_cosmos_videos()
    nasa_data = scrape_nasa()
    
    all_new_data = text_data + video_data + nasa_data
    
    if not all_new_data:
        print("No new data found.")
        exit()
        
    if os.path.exists(corpus_path):
        with open(corpus_path, 'r') as file:
            current_data = yaml.safe_load(file) or {}
    else:
        current_data = {'categories': ['astronomy'], 'conversations': []}
        
    if 'conversations' not in current_data:
        current_data['conversations'] = []

    knowledge_map = {}
    for item in current_data['conversations']:
        knowledge_map[item[0].lower()] = item[1]
    
    updates_count = 0
    adds_count = 0

    for question, new_answer in all_new_data:
        if question in knowledge_map:
            if knowledge_map[question] != new_answer:
                knowledge_map[question] = new_answer
                updates_count += 1
                print(f"   [updated] {question}")
        else:
            knowledge_map[question] = new_answer
            adds_count += 1
            print(f"   [new] {question}")
    
    final_conversations = [[q, a] for q, a in knowledge_map.items()]
    current_data['conversations'] = final_conversations

    with open(corpus_path, 'w') as file:
        yaml.dump(current_data, file, default_flow_style=False, allow_unicode=True)
        
    print(f"\nAdded {adds_count} new and updated {updates_count} existing answers.")