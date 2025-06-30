from app.DiffChatManager import DiffChatManager

if __name__ == '__main__':
    manager = DiffChatManager()
    role = "QA"
    feature = "BASEL-1"
    manager.upload_diff_version("v3.txt")
    thread_id = manager.create_thread(role, feature, "3")
    result = manager.send_message(
        role,
        thread_id,
        "Что нужно протестировать?"
    )
    print(result)

