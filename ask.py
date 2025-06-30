#!/usr/bin/env python3
import argparse

from DiffChatManager import DiffChatManager


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GPT Ассистент для CLI")
    parser.add_argument("--diff", required=True, help="Путь до файла с изменениями (расширение txt, имя файла желательно давать как sha коммита, так потом удобнее искать в file store)")
    parser.add_argument("--prompt", required=True, help="Вопрос для ассистента")
    parser.add_argument("--role", required=True, help="Имя роли ассистента (см. config.json)")
    parser.add_argument("--feature", required=True, help="Jira-ID фичи")
    parser.add_argument("--version", required=True, help="Номер версии (можно sha коммита если нет версионирования)")
    args = parser.parse_args()

    manager = DiffChatManager()
    manager.upload_diff_version(args.diff)
    thread_id = manager.create_thread(args.role, args.feature, args.version)
    result = manager.send_message(args.role,thread_id,args.prompt)

    print(f"<<< QUESTION:\n{args.prompt}\n\n")
    print(f">>> ANSWER:\n{result}\n\n")
