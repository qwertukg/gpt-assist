from app.DiffChatManager import DiffChatManager

if __name__ == '__main__':
    manager = DiffChatManager()
    role = "TechLead"
    feature = "BASEL-1"
    manager.upload_diff_version("v3.txt")
    thread_id = manager.create_thread(role, feature, "3")
    result = manager.send_message(
        role,
        thread_id,
        "Как изменилась эта Фича по сравнению c предыдущей версией?"
    )
    print(result)

