from app.DiffChatManager import DiffChatManager

if __name__ == '__main__':
    manager = DiffChatManager()
    sha = "feature_v4"
    manager.upload_diff_version(sha + ".txt")
    thread_id = manager.create_thread({"commit": "sha_" + sha, "feature": "BASEL-3"})
    result = manager.send_message(
        "TechLead",
        thread_id,
        "Как изменилась эта Фича по сравнению с BASEL-1?"
    )
    print(result)


