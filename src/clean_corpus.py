import yaml
import os
import html
import re

# 1. SETUP PATHS
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_script_dir)
corpus_path = os.path.join(project_root, 'data', 'astronomy_corpus.yml')

def rigorous_clean(text):
    if not isinstance(text, str):
        return str(text)

    text = html.unescape(text)
    text = text.replace('\r', ' ').replace('\t', ' ').replace('\xa0', ' ')

    # Remove carriage returns but keep \n newlines
    text = text.replace('\r', '')
    # Only replace horizontal spaces, leave newlines alone
    text = re.sub(r'[ \t\xa0]+', ' ', text)

    return text.strip()

def run_cleaning():    
    if not os.path.exists(corpus_path):
        print("Error: File not found!")
        return

    with open(corpus_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if not data or 'conversations' not in data:
        print("[error] invalid YAML structure.")
        return

    conversations = data['conversations']
    cleaned_count = 0

    new_conversations = []
    for pair in conversations:
        question = pair[0]
        answer = pair[1]

        clean_q = rigorous_clean(question).lower()
        clean_a = rigorous_clean(answer)

        new_conversations.append([clean_q, clean_a])
        cleaned_count += 1

    data['conversations'] = new_conversations

    with open(corpus_path, 'w', encoding='utf-8') as f:
        yaml.dump(
            data, 
            f, 
            default_flow_style=False, 
            allow_unicode=True, 
            width=1000
        )

    print(f"cleaned {cleaned_count} Q&A pairs.")

if __name__ == "__main__":
    run_cleaning()