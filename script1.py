from DiffChatManager import DiffChatManager

if __name__ == '__main__':
    manager = DiffChatManager()
    role = "TechLead"
    feature = "BASEL-1"
    manager.upload_diff_version("v1.txt")
    thread_id = manager.create_thread(role, feature, "1")
    result = manager.send_message(
        role,
        thread_id,
        "Как изменилась эта Фича по сравнению c предыдущей версией?"
    )
    print(result)



