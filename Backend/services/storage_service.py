from config import supabase, BUCKET_NAME

def upload_file(file, user_id, session_id):
    file_name = file.filename
    path = f"{user_id}/{session_id}/{file_name}"
    
    #  convert to bytes
    file_bytes = file.read()

    response = supabase.storage.from_(BUCKET_NAME).upload(
        path=path,
        file=file_bytes,
        file_options={
            "content-type": "application/pdf",
            "upsert": "true"
        }
    )

    return {
        "path": path,
        "file_name": file_name,
        "response": str(response)
    }


def download_file(user_id, session_id, file_name):
    path = f"{user_id}/{session_id}/{file_name}"

    file_bytes = supabase.storage.from_(BUCKET_NAME).download(path)
    return file_bytes


def list_files(user_id, session_id):
    path = f"{user_id}/{session_id}"

    files = supabase.storage.from_(BUCKET_NAME).list(path)

    # Extract only file names
    file_names = [f["name"] for f in files]

    return file_names