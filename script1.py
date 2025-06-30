from app.DiffChatManager import DiffChatManager

if __name__ == '__main__':
    manager = DiffChatManager()
    sha = "feature_v1"
    manager.upload_diff_version(sha + ".txt")
    thread_id = manager.create_thread({"commit": "sha_" + sha, "feature": "BASEL-1"})
    result = manager.send_message(
        "TechLead",
        thread_id,
        "Что делает код этой фичи?"
    )
    print(result)



